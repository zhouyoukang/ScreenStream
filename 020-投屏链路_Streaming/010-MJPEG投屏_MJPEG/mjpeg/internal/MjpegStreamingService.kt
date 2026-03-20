package info.dvkr.screenstream.mjpeg.internal

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ComponentCallbacks
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Shader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.media.MediaFormat
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.os.Message
import android.os.PowerManager
import android.widget.Toast
import androidx.annotation.AnyThread
import androidx.annotation.MainThread
import androidx.window.layout.WindowMetricsCalculator
import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import info.dvkr.screenstream.mjpeg.MjpegModuleService
import info.dvkr.screenstream.mjpeg.R
import info.dvkr.screenstream.mjpeg.settings.MjpegSettings
import info.dvkr.screenstream.mjpeg.ui.MjpegError
import info.dvkr.screenstream.mjpeg.ui.MjpegState
import kotlinx.coroutines.CompletableJob
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.android.asCoroutineDispatcher
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.delay
import kotlin.math.max
import kotlin.math.min
import java.security.SecureRandom
import androidx.core.graphics.createBitmap
import androidx.core.graphics.scale
import androidx.core.graphics.toColorInt

internal class MjpegStreamingService(
    private val service: MjpegModuleService,
    private val mutableMjpegStateFlow: MutableStateFlow<MjpegState>,
    private val networkHelper: NetworkHelper,
    private val mjpegSettings: MjpegSettings
) : HandlerThread("MJPEG-HT", android.os.Process.THREAD_PRIORITY_DISPLAY), Handler.Callback {

    private val powerManager: PowerManager = service.application.getSystemService(PowerManager::class.java)
    private val projectionManager = service.application.getSystemService(MediaProjectionManager::class.java)
    private val mainHandler: Handler by lazy(LazyThreadSafetyMode.NONE) { Handler(Looper.getMainLooper()) }
    private val handler: Handler by lazy(LazyThreadSafetyMode.NONE) { Handler(looper, this) }
    private val coroutineDispatcher: CoroutineDispatcher by lazy(LazyThreadSafetyMode.NONE) { handler.asCoroutineDispatcher("MJPEG-HT_Dispatcher") }
    private val supervisorJob = SupervisorJob()
    private val coroutineScope by lazy(LazyThreadSafetyMode.NONE) { CoroutineScope(supervisorJob + coroutineDispatcher) }
    private val bitmapStateFlow = MutableStateFlow(createBitmap(1, 1))
    private val h264SharedFlow = MutableSharedFlow<H264Frame>(replay = 1, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    private val h265SharedFlow = MutableSharedFlow<H264Frame>(replay = 1, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    private val audioStreamer = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) AudioStreamer(service) else null

    private val httpServer by lazy(mode = LazyThreadSafetyMode.NONE) {
        HttpServer(
            service,
            mjpegSettings,
            bitmapStateFlow.asStateFlow(),
            h264SharedFlow.onSubscription { lastH264ConfigFrame?.let { emit(it) } },
            h265SharedFlow.onSubscription { lastH265ConfigFrame?.let { emit(it) } },
            audioStreamer?.audioFlow,
            ::sendEvent,
            { sendEvent(InternalEvent.RequestKeyFrame) }
        )
    }

    // All Volatiles vars must be write on this (WebRTC-HT) thread
    @Volatile private var wakeLock: PowerManager.WakeLock? = null
    // All Volatiles vars must be write on this (WebRTC-HT) thread

    // All vars must be read/write on this (WebRTC-HT) thread
    private var startBitmap: Bitmap? = null
    private var pendingServer: Boolean = true
    private var deviceConfiguration: Configuration = Configuration(service.resources.configuration)
    private var netInterfaces: List<MjpegNetInterface> = emptyList()
    private var clients: List<MjpegState.Client> = emptyList()
    private var slowClients: List<MjpegState.Client> = emptyList()
    private var traffic: List<MjpegState.TrafficPoint> = emptyList()
    private var isStreaming: Boolean = false
    private var waitingForPermission: Boolean = false
    private var mediaProjectionIntent: Intent? = null
    private var mediaProjection: MediaProjection? = null
    private var bitmapCapture: BitmapCapture? = null
    private var h264Encoder: H264Encoder? = null
    private var h264VirtualDisplay: android.hardware.display.VirtualDisplay? = null
    @Volatile private var lastH264ConfigFrame: H264Frame? = null
    @Volatile private var lastH265ConfigFrame: H264Frame? = null
    private var cloudRelayClient: CloudRelayClient? = null
    // private var webRtcP2PClient: WebRtcP2PClient? = null // WIP: needs webrtc dep
    private var currentError: MjpegError? = null
    private var previousError: MjpegError? = null
    // All vars must be read/write on this (WebRTC-HT) thread

    internal sealed class InternalEvent(priority: Int) : MjpegEvent(priority) {
        data class InitState(val clearIntent: Boolean = true) : InternalEvent(Priority.RESTART_IGNORE)
        data class DiscoverAddress(val reason: String, val attempt: Int) : InternalEvent(Priority.RESTART_IGNORE)
        data class StartServer(val interfaces: List<MjpegNetInterface>) : InternalEvent(Priority.RESTART_IGNORE)
        data object StartStream : InternalEvent(Priority.RESTART_IGNORE)
        data object StartStopFromWebPage : InternalEvent(Priority.RESTART_IGNORE)
        data object ScreenOff : InternalEvent(Priority.RESTART_IGNORE)
        data class ConfigurationChange(val newConfig: Configuration) : InternalEvent(Priority.RESTART_IGNORE) {
            override fun toString(): String = "ConfigurationChange"
        }
        data class CapturedContentResize(val width: Int, val height: Int) : InternalEvent(Priority.RESTART_IGNORE)
        data class Clients(val clients: List<MjpegState.Client>) : InternalEvent(Priority.RESTART_IGNORE)
        data class RestartServer(val reason: RestartReason) : InternalEvent(Priority.RESTART_IGNORE)
        data object UpdateStartBitmap : InternalEvent(Priority.RESTART_IGNORE)
        data object RequestKeyFrame : InternalEvent(Priority.RESTART_IGNORE)
        data class UpdateBitrate(val latency: Long) : InternalEvent(Priority.RESTART_IGNORE)

        data class Error(val error: MjpegError) : InternalEvent(Priority.RECOVER_IGNORE)

        data class Destroy(val destroyJob: CompletableJob) : InternalEvent(Priority.DESTROY_IGNORE)
        data class Traffic(val time: Long, val traffic: List<MjpegState.TrafficPoint>) : InternalEvent(Priority.DESTROY_IGNORE) {
            override fun toString(): String = "Traffic(time=$time)"
        }
    }

    internal sealed class RestartReason(private val msg: String) {
        object ConnectionChanged : RestartReason("")
        class SettingsChanged(msg: String) : RestartReason(msg)
        class NetworkSettingsChanged(msg: String) : RestartReason(msg)

        override fun toString(): String = "${javaClass.simpleName}[$msg]"
    }

    private val componentCallback = object : ComponentCallbacks {
        override fun onConfigurationChanged(newConfig: Configuration) = sendEvent(InternalEvent.ConfigurationChange(newConfig))
        override fun onLowMemory() = Unit
    }

    private val projectionCallback = object : MediaProjection.Callback() {
        override fun onStop() {
            XLog.i(this@MjpegStreamingService.getLog("MediaProjection.Callback", "onStop"))
            sendEvent(MjpegEvent.Intentable.StopStream("MediaProjection.Callback"))
        }

        // TODO https://android-developers.googleblog.com/2024/03/enhanced-screen-sharing-capabilities-in-android-14.html
        override fun onCapturedContentVisibilityChanged(isVisible: Boolean) {
            XLog.i(this@MjpegStreamingService.getLog("MediaProjection.Callback", "onCapturedContentVisibilityChanged: $isVisible"))
        }

        override fun onCapturedContentResize(width: Int, height: Int) {
            XLog.i(this@MjpegStreamingService.getLog("MediaProjection.Callback", "onCapturedContentResize: width: $width, height: $height"))
            sendEvent(InternalEvent.CapturedContentResize(width, height))
        }
    }

    init {
        XLog.d(getLog("init"))
    }

    @MainThread
    override fun start() {
        super.start()
        XLog.d(getLog("start"))

        mutableMjpegStateFlow.value = MjpegState()
        sendEvent(InternalEvent.InitState())
        sendEvent(InternalEvent.DiscoverAddress("ServiceStart", 0))

        coroutineScope.launch {
            if (mjpegSettings.data.value.enablePin && mjpegSettings.data.value.newPinOnAppStart) {
                mjpegSettings.updateData { copy(pin = randomPin()) }
            }
        }

        service.startListening(
            supervisorJob,
            onScreenOff = { sendEvent(InternalEvent.ScreenOff) },
            onConnectionChanged = { sendEvent(InternalEvent.RestartServer(RestartReason.ConnectionChanged)) }
        )

        mjpegSettings.data.map { it.htmlBackColor }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.UpdateStartBitmap)
        }
        mjpegSettings.data.map { it.enablePin }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.RestartServer(RestartReason.SettingsChanged(MjpegSettings.Key.ENABLE_PIN.name)))
        }
        mjpegSettings.data.map { it.pin }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.RestartServer(RestartReason.SettingsChanged(MjpegSettings.Key.PIN.name)))
        }
        mjpegSettings.data.map { it.blockAddress }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.RestartServer(RestartReason.SettingsChanged(MjpegSettings.Key.BLOCK_ADDRESS.name)))
        }
        mjpegSettings.data.map { it.interfaceFilter }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.RestartServer(RestartReason.NetworkSettingsChanged(MjpegSettings.Key.INTERFACE_FILTER.name)))
        }
        mjpegSettings.data.map { it.addressFilter }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.RestartServer(RestartReason.NetworkSettingsChanged(MjpegSettings.Key.ADDRESS_FILTER.name)))
        }
        mjpegSettings.data.map { it.enableIPv4 }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.RestartServer(RestartReason.NetworkSettingsChanged(MjpegSettings.Key.ENABLE_IPV4.name)))
        }
        mjpegSettings.data.map { it.enableIPv6 }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.RestartServer(RestartReason.NetworkSettingsChanged(MjpegSettings.Key.ENABLE_IPV6.name)))
        }
        mjpegSettings.data.map { it.serverPort }.listenForChange(coroutineScope, 1) {
            sendEvent(InternalEvent.RestartServer(RestartReason.NetworkSettingsChanged(MjpegSettings.Key.SERVER_PORT.name)))
        }
    }

    @MainThread
    suspend fun destroyService() {
        XLog.d(getLog("destroyService"))

        wakeLock?.apply { if (isHeld) release() }
        supervisorJob.cancel()

        val destroyJob = Job()
        sendEvent(InternalEvent.Destroy(destroyJob))
        withTimeoutOrNull(3000) { destroyJob.join() } ?: XLog.w(getLog("destroyService", "Timeout"))

        handler.removeCallbacksAndMessages(null)

        service.stopSelf()

        quit() // Only after everything else is destroyed
    }

    private var destroyPending: Boolean = false

    @AnyThread
    @Synchronized
    internal fun sendEvent(event: MjpegEvent, timeout: Long = 0) {
        if (destroyPending) {
            XLog.w(getLog("sendEvent", "Pending destroy: Ignoring event => $event"))
            return
        }
        if (event is InternalEvent.Destroy) destroyPending = true

        if (timeout > 0) XLog.d(getLog("sendEvent", "New event [Timeout: $timeout] => $event"))
        else XLog.v(getLog("sendEvent", "New event => $event"))

        if (event is InternalEvent.RestartServer) {
            handler.removeMessages(MjpegEvent.Priority.RESTART_IGNORE)
        }
        if (event is MjpegEvent.Intentable.RecoverError) {
            handler.removeMessages(MjpegEvent.Priority.RESTART_IGNORE)
            handler.removeMessages(MjpegEvent.Priority.RECOVER_IGNORE)
        }
        if (event is InternalEvent.Destroy) {
            handler.removeMessages(MjpegEvent.Priority.RESTART_IGNORE)
            handler.removeMessages(MjpegEvent.Priority.RECOVER_IGNORE)
            handler.removeMessages(MjpegEvent.Priority.DESTROY_IGNORE)
        }

        handler.sendMessageDelayed(handler.obtainMessage(event.priority, event), timeout)
    }

    override fun handleMessage(msg: Message): Boolean = runBlocking(Dispatchers.Unconfined) {
        val event: MjpegEvent = msg.obj as MjpegEvent
        try {
            if (event !is InternalEvent.Traffic) {
                XLog.d(this@MjpegStreamingService.getLog("handleMessage", "Event [$event] Current state: [${getStateString()}]"))
            }
            processEvent(event)
        } catch (cause: Throwable) {
            XLog.e(this@MjpegStreamingService.getLog("handleMessage.catch", cause.toString()), cause)

            mediaProjectionIntent = null
            stopStream()

            currentError = if (cause is MjpegError) cause else MjpegError.UnknownError(cause)
        } finally {
            if (event !is InternalEvent.Traffic) {
                XLog.d(this@MjpegStreamingService.getLog("handleMessage", "Done [$event] New state: [${getStateString()}]"))
            }
            if (event is InternalEvent.Destroy) event.destroyJob.complete()
            publishState()
        }

        true
    }

    // On MJPEG-HT only
    private suspend fun processEvent(event: MjpegEvent) {
        when (event) {
            is InternalEvent.InitState -> {
                pendingServer = true
                deviceConfiguration = Configuration(service.resources.configuration)
                netInterfaces = emptyList()
                clients = emptyList()
                slowClients = emptyList()
                isStreaming = false
                waitingForPermission = false
                if (event.clearIntent) mediaProjectionIntent = null
                mediaProjection = null
                bitmapCapture = null

                currentError = null
            }

            is InternalEvent.DiscoverAddress -> {
                if (pendingServer.not()) httpServer.stop(false)

                val newInterfaces = networkHelper.getNetInterfaces(
                    mjpegSettings.data.value.interfaceFilter,
                    mjpegSettings.data.value.addressFilter,
                    mjpegSettings.data.value.enableIPv4,
                    mjpegSettings.data.value.enableIPv6,
                )

                if (newInterfaces.isNotEmpty()) {
                    sendEvent(InternalEvent.StartServer(newInterfaces))
                } else {
                    if (event.attempt < 3) {
                        sendEvent(InternalEvent.DiscoverAddress(event.reason, event.attempt + 1), 1000)
                    } else {
                        netInterfaces = emptyList()
                        clients = emptyList()
                        slowClients = emptyList()
                        currentError = MjpegError.AddressNotFoundException
                    }
                }
            }

            is InternalEvent.StartServer -> {
                if (pendingServer.not()) httpServer.stop(false)
                httpServer.start(event.interfaces.toList())

                if (isStreaming.not() && mjpegSettings.data.value.htmlShowPressStart) bitmapStateFlow.value = getStartBitmap()

                netInterfaces = event.interfaces
                pendingServer = false
            }

            is InternalEvent.StartStopFromWebPage -> when {
                isStreaming -> sendEvent(MjpegEvent.Intentable.StopStream("StartStopFromWebPage"))
                pendingServer.not() && currentError == null -> waitingForPermission = true
            }

            is InternalEvent.StartStream -> {
                mediaProjectionIntent?.let {
                    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                        sendEvent(MjpegEvent.StartProjection(it))
                    } else {
                        waitingForPermission = true
                    }
                } ?: run {
                    waitingForPermission = true
                }
            }

            is MjpegEvent.CastPermissionsDenied -> waitingForPermission = false

            is MjpegEvent.StartProjection ->
                if (pendingServer) {
                    waitingForPermission = false
                    XLog.w(getLog("MjpegEvent.StartProjection", "Server is not ready. Ignoring"))
                } else if (isStreaming) {
                    waitingForPermission = false
                    XLog.w(getLog("MjpegEvent.StartProjection", "Already streaming"))
                } else {
                    waitingForPermission = false
                    service.startForeground()

                    // TODO Starting from Android R, if your application requests the SYSTEM_ALERT_WINDOW permission, and the user has
                    //  not explicitly denied it, the permission will be automatically granted until the projection is stopped.
                    //  The permission allows your app to display user controls on top of the screen being captured.
                    val mediaProjection = projectionManager.getMediaProjection(Activity.RESULT_OK, event.intent)!!.apply {
                        registerCallback(projectionCallback, Handler(Looper.getMainLooper()))
                    }

                    val streamCodec = mjpegSettings.data.value.streamCodec
                    val isMjpeg = streamCodec == MjpegSettings.Values.STREAM_CODEC_MJPEG

                    if (isMjpeg) {
                        val bitmapCapture = BitmapCapture(service, mjpegSettings, mediaProjection, bitmapStateFlow) { error ->
                            sendEvent(InternalEvent.Error(error))
                        }
                        val captureStarted = bitmapCapture.start()
                        if (captureStarted && Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                            if (Build.VERSION.SDK_INT != Build.VERSION_CODES.S || !Build.MANUFACTURER.equals("Xiaomi", ignoreCase = true)) {
                                mediaProjectionIntent = event.intent
                                service.registerComponentCallbacks(componentCallback)
                            }
                        }
                        this@MjpegStreamingService.bitmapCapture = bitmapCapture
                    } else {
                        // H.264 / H.265 Web mode: use a single VirtualDisplay with MediaCodec surface.
                        // Avoid running BitmapCapture in parallel to prevent MediaProjection invalidation on Android 14+/15.
                        val bounds = WindowMetricsCalculator.getOrCreate().computeMaximumWindowMetrics(service).bounds
                        // 公网投屏: 分辨率由DataStore resizeFactor控制 (25=270p, 50=540p, 75=720p, 100=原生)
                        val scaleFactor = mjpegSettings.data.value.resizeFactor.coerceIn(10, 100) / 100.0
                        var width = (bounds.width() * scaleFactor).toInt()
                        var height = (bounds.height() * scaleFactor).toInt()
                        if (width % 2 != 0) width--
                        if (height % 2 != 0) height--
                        XLog.i(getLog("H264", "Encode resolution: ${width}x${height} (scale=${(scaleFactor*100).toInt()}% of ${bounds.width()}x${bounds.height()})"))

                        val mimeType = if (streamCodec == MjpegSettings.Values.STREAM_CODEC_H265)
                            MediaFormat.MIMETYPE_VIDEO_HEVC
                        else
                            MediaFormat.MIMETYPE_VIDEO_AVC

                        // Resolution-adaptive bitrate: ~8 bits/pixel @ target fps for sharp LAN quality
                        // 1080x2400@30fps → ~12Mbps, 720x1600@30fps → ~6Mbps, 540x1200@30fps → ~3Mbps
                        val pixels = width.toLong() * height.toLong()
                        val adaptiveBitRate = (pixels * 8 * 30 / 1000000).toInt().coerceIn(3000000, 20000000)
                        XLog.i(getLog("H264", "Adaptive bitrate: ${adaptiveBitRate/1000}kbps for ${width}x${height}"))

                        val encoder = H264Encoder(
                            width = width,
                            height = height,
                            densityDpi = (service.resources.configuration.densityDpi * scaleFactor).toInt(),
                            mimeType = mimeType,
                            bitRate = adaptiveBitRate,
                            frameRate = 30
                        ) { frame ->
                            if (frame.type == H264Frame.TYPE_CONFIG) {
                                if (streamCodec == MjpegSettings.Values.STREAM_CODEC_H265) {
                                    lastH265ConfigFrame = frame
                                } else {
                                    lastH264ConfigFrame = frame
                                }
                            }
                            val targetFlow = if (streamCodec == MjpegSettings.Values.STREAM_CODEC_H265) h265SharedFlow else h264SharedFlow
                            coroutineScope.launch { targetFlow.emit(frame) }
                        }

                        currentBitrate = adaptiveBitRate // Sync ABR starting point

                        val surface = encoder.getInputSurface()
                        if (surface != null) {
                            h264VirtualDisplay = mediaProjection.createVirtualDisplay(
                                "ScreenStream-Video",
                                width,
                                height,
                                service.resources.configuration.densityDpi,
                                android.hardware.display.DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                                surface,
                                null,
                                handler
                            )
                            h264Encoder = encoder
                        }
                    }

                    @Suppress("DEPRECATION")
                    @SuppressLint("WakelockTimeout")
                    if (Build.MANUFACTURER !in listOf("OnePlus", "OPPO") && mjpegSettings.data.value.keepAwake) {
                        val flags = PowerManager.SCREEN_DIM_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP
                        wakeLock = powerManager.newWakeLock(flags, "ScreenStream::MJPEG-Tag").apply { acquire() }
                    }

                    this@MjpegStreamingService.isStreaming = true
                    this@MjpegStreamingService.mediaProjection = mediaProjection

                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        audioStreamer?.start(mediaProjection)
                    }

                    // Auto-connect to cloud relay for public network streaming (both MJPEG and H264)
                    try {
                        val relayH264 = if (!isMjpeg) h264SharedFlow.onSubscription { lastH264ConfigFrame?.let { emit(it) } } else null
                        val relayBitmap = if (isMjpeg) bitmapStateFlow else null
                        cloudRelayClient = CloudRelayClient(
                            context = service,
                            h264Flow = relayH264,
                            bitmapFlow = relayBitmap
                        ).apply {
                            setStateListener { connected, url, viewers ->
                                XLog.i(getLog("CloudRelay", "connected=$connected viewers=$viewers url=$url mode=${if (isMjpeg) "MJPEG" else "H264"}"))
                                publishState()
                                if (connected && roomCode.isNotEmpty()) {
                                    speakRoomCode(roomCode)
                                }
                            }
                            start()
                        }
                        XLog.i(getLog("CloudRelay", "Started (${if (isMjpeg) "MJPEG" else "H264"}). URL: ${cloudRelayClient?.viewerUrl}"))
                    } catch (e: Exception) {
                        XLog.e(getLog("CloudRelay", "Failed to start"), e)
                    }

                    // WIP: WebRTC P2P disabled (needs webrtc dependency)
                    // try { webRtcP2PClient = WebRtcP2PClient(...) } catch (e: Exception) { }
                }

            is MjpegEvent.Intentable.StopStream -> {
                stopStream()

                if (mjpegSettings.data.value.enablePin && mjpegSettings.data.value.autoChangePin)
                    mjpegSettings.updateData { copy(pin = randomPin()) }

                if (mjpegSettings.data.value.htmlShowPressStart) bitmapStateFlow.value = getStartBitmap()
            }

            is InternalEvent.ScreenOff -> if (isStreaming && mjpegSettings.data.value.stopOnSleep)
                sendEvent(MjpegEvent.Intentable.StopStream("ScreenOff"))

            is InternalEvent.ConfigurationChange -> {
                if (isStreaming) {
                    val configDiff = deviceConfiguration.diff(event.newConfig)
                    if (
                        configDiff and ActivityInfo.CONFIG_ORIENTATION != 0 || configDiff and ActivityInfo.CONFIG_SCREEN_LAYOUT != 0 ||
                        configDiff and ActivityInfo.CONFIG_SCREEN_SIZE != 0 || configDiff and ActivityInfo.CONFIG_DENSITY != 0
                    ) {
                        bitmapCapture?.resize()
                    } else {
                        XLog.d(getLog("ConfigurationChange", "No change relevant for streaming. Ignoring."))
                    }
                } else {
                    XLog.d(getLog("ConfigurationChange", "Not streaming. Ignoring."))
                }
                deviceConfiguration = Configuration(event.newConfig)
            }

            is InternalEvent.CapturedContentResize -> {
                if (isStreaming) {
                    bitmapCapture?.resize(event.width, event.height)
                } else {
                    XLog.d(getLog("CapturedContentResize", "Not streaming. Ignoring."))
                }
            }

            is InternalEvent.RestartServer -> {
                if (mjpegSettings.data.value.stopOnConfigurationChange) stopStream()

                waitingForPermission = false
                if (pendingServer) {
                    XLog.d(getLog("processEvent", "RestartServer: No running server."))
                    if (currentError == MjpegError.AddressNotFoundException) currentError = null
                } else {
                    httpServer.stop(event.reason is RestartReason.SettingsChanged)
                    if (mjpegSettings.data.value.stopOnConfigurationChange) {
                        sendEvent(InternalEvent.InitState(false))
                    } else {
                        pendingServer = true
                        netInterfaces = emptyList()
                        clients = emptyList()
                        slowClients = emptyList()
                        currentError = null
                    }
                }
                sendEvent(InternalEvent.DiscoverAddress("RestartServer", 0))
            }

            InternalEvent.UpdateStartBitmap -> {
                startBitmap = null
                if (isStreaming.not() && mjpegSettings.data.value.htmlShowPressStart) bitmapStateFlow.value = getStartBitmap()
            }

            InternalEvent.RequestKeyFrame -> {
                coroutineScope.launch {
                    repeat(5) {
                        h264Encoder?.forceKeyFrame()
                        delay(200)
                    }
                }
            }

            is MjpegEvent.Intentable.RecoverError -> {
                stopStream()
                httpServer.stop(true)

                handler.removeMessages(MjpegEvent.Priority.RESTART_IGNORE)
                handler.removeMessages(MjpegEvent.Priority.RECOVER_IGNORE)

                sendEvent(InternalEvent.InitState(true))
                sendEvent(InternalEvent.DiscoverAddress("RecoverError", 0))
            }

            is InternalEvent.Destroy -> {
                stopStream()
                cloudRelayClient?.destroy()
                cloudRelayClient = null
                // webRtcP2PClient?.destroy() // WIP
                // webRtcP2PClient = null
                httpServer.destroy()
                currentError = null
            }

            is InternalEvent.Error -> currentError = event.error

            is InternalEvent.Clients -> {
                clients = event.clients
                if (mjpegSettings.data.value.notifySlowConnections) {
                    val currentSlowClients = event.clients.filter { it.state == MjpegState.Client.State.SLOW_CONNECTION }.toList()
                    if (slowClients.containsAll(currentSlowClients).not()) {
                        mainHandler.post { Toast.makeText(service, R.string.mjpeg_slow_client_connection, Toast.LENGTH_LONG).show() }
                    }
                    slowClients = currentSlowClients
                }
            }

            is InternalEvent.Traffic -> traffic = event.traffic

            is MjpegEvent.CreateNewPin -> when {
                destroyPending -> XLog.i(
                    getLog("CreateNewPin", "DestroyPending. Ignoring"),
                    IllegalStateException("CreateNewPin: DestroyPending")
                )

                isStreaming -> XLog.i(getLog("CreateNewPin", "Streaming. Ignoring."), IllegalStateException("CreateNewPin: Streaming."))
                mjpegSettings.data.value.enablePin -> mjpegSettings.updateData { copy(pin = randomPin()) } // will restart server
            }

            is InternalEvent.UpdateBitrate -> handleBitrateUpdate(event.latency)

            else -> throw IllegalArgumentException("Unknown MjpegEvent: ${event::class.java}")
        }
    }

    // Inline Only
    @Suppress("NOTHING_TO_INLINE")
    private inline fun stopStream() {
        if (isStreaming) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                service.unregisterComponentCallbacks(componentCallback)
            }
            bitmapCapture?.destroy()
            bitmapCapture = null
            mediaProjection?.unregisterCallback(projectionCallback)
            mediaProjection?.stop()
            mediaProjection = null

            isStreaming = false

            audioStreamer?.stop()
        } else {
            XLog.d(getLog("stopStream", "Not streaming. Ignoring."))
        }

        try {
            cloudRelayClient?.stop()
            cloudRelayClient = null
        } catch (e: Exception) {
            XLog.e(getLog("stopStream", "CloudRelay Stop Error"), e)
        }

        try {
            // webRtcP2PClient?.stop() // WIP
            // webRtcP2PClient = null
        } catch (e: Exception) {
            XLog.e(getLog("stopStream", "WebRTC-P2P Stop Error"), e)
        }

        try {
            tts?.stop()
            tts?.shutdown()
            tts = null
            ttsReady = false
            lastSpokenCode = ""
        } catch (e: Exception) {
            XLog.w(getLog("stopStream", "TTS cleanup error: ${e.message}"))
        }

        try {
            h264VirtualDisplay?.release()
            h264VirtualDisplay = null
            h264Encoder?.stop()
            h264Encoder = null
        } catch (e: Exception) {
            XLog.e(getLog("stopStream", "H264 Stop Error"), e)
        }

        wakeLock?.apply { if (isHeld) release() }
        wakeLock = null

        service.stopForeground()
    }

    // Inline Only
    @Suppress("NOTHING_TO_INLINE")
    private inline fun getStateString() =
        "Pending Dest/Server: $destroyPending/$pendingServer, Streaming:$isStreaming, WFP:$waitingForPermission, Clients:${clients.size}, Error:${currentError}"

    // Inline Only
    @Suppress("NOTHING_TO_INLINE")
    private inline fun publishState() {
        val state = MjpegState(
            isBusy = pendingServer || destroyPending || waitingForPermission || currentError != null,
            serverNetInterfaces = netInterfaces.map {
                MjpegState.ServerNetInterface(it.label, it.buildUrl(mjpegSettings.data.value.serverPort))
            }.sortedBy { it.fullAddress },
            waitingCastPermission = waitingForPermission,
            isStreaming = isStreaming,
            pin = MjpegState.Pin(mjpegSettings.data.value.enablePin, mjpegSettings.data.value.pin, mjpegSettings.data.value.hidePinOnStart),
            clients = clients.toList(),
            traffic = traffic.toList(),
            error = currentError,
            cloudRelayRoomCode = cloudRelayClient?.roomCode ?: "",
            cloudRelayViewerUrl = cloudRelayClient?.viewerUrl ?: "",
            cloudRelayConnected = cloudRelayClient?.isConnected ?: false,
            cloudRelayViewerCount = cloudRelayClient?.viewerCount ?: 0
        )

        mutableMjpegStateFlow.value = state

        if (previousError != currentError) {
            previousError = currentError
            currentError?.let { service.showErrorNotification(it) } ?: service.hideErrorNotification()
        }
    }

    private val secureRandom = SecureRandom()
    private fun randomPin(): String = secureRandom.nextInt(10).toString() + secureRandom.nextInt(10).toString() +
            secureRandom.nextInt(10).toString() + secureRandom.nextInt(10).toString() +
            secureRandom.nextInt(10).toString() + secureRandom.nextInt(10).toString()

    private var tts: android.speech.tts.TextToSpeech? = null
    private var ttsReady = false
    private var lastSpokenCode = ""

    private fun speakRoomCode(code: String) {
        if (code == lastSpokenCode) return
        lastSpokenCode = code

        val digitNames = mapOf(
            '0' to "零", '1' to "一", '2' to "二", '3' to "三", '4' to "四",
            '5' to "五", '6' to "六", '7' to "七", '8' to "八", '9' to "九"
        )
        val spoken = code.map { digitNames[it] ?: it.toString() }.joinToString(" ")
        val text = "您的连接码是 $spoken"

        if (tts == null) {
            tts = android.speech.tts.TextToSpeech(service) { status ->
                if (status == android.speech.tts.TextToSpeech.SUCCESS) {
                    ttsReady = true
                    tts?.language = java.util.Locale.CHINESE
                    tts?.setSpeechRate(0.8f)
                    tts?.speak(text, android.speech.tts.TextToSpeech.QUEUE_FLUSH, null, "room_code")
                    XLog.i(getLog("TTS", "Speaking room code: $code"))
                }
            }
        } else if (ttsReady) {
            tts?.speak(text, android.speech.tts.TextToSpeech.QUEUE_FLUSH, null, "room_code")
            XLog.i(getLog("TTS", "Speaking room code: $code"))
        }
    }

    private fun getStartBitmap(): Bitmap {
        startBitmap?.let { return it }

        val screenSize = WindowMetricsCalculator.getOrCreate().computeMaximumWindowMetrics(service).bounds
        val bitmap = createBitmap(max(screenSize.width(), 600), max(screenSize.height(), 800))

        var width = min(bitmap.width.toFloat(), 1536F)
        val height = min(bitmap.height.toFloat(), width * 0.75F)
        width = height / 0.75F

        val left = max((bitmap.width - width) / 2F, 0F)
        val top = max((bitmap.height - height) / 2F, 0F)
        val right = bitmap.width - left
        val bottom = (bitmap.height + height) / 2
        val backRect = RectF(left, top, right, bottom)
        val canvas = Canvas(bitmap).apply {
            drawColor(mjpegSettings.data.value.htmlBackColor)
            val shader = LinearGradient(
                backRect.left, backRect.top, backRect.left, backRect.bottom,
                "#144A74".toColorInt(), "#001D34".toColorInt(), Shader.TileMode.CLAMP
            )
            drawRoundRect(backRect, 32F, 32F, Paint().apply { setShader(shader) })
        }

        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 26F / 600 * backRect.width(); color = Color.WHITE }
        val logoSize = (min(backRect.width(), backRect.height()) * 0.7).toInt()
        val logo = service.getFileFromAssets("logo.png").run { BitmapFactory.decodeByteArray(this, 0, size) }.scale(logoSize, logoSize)
        canvas.drawBitmap(logo, backRect.left + (backRect.width() - logo.width) / 2, backRect.top, paint)

        val message = service.getString(R.string.mjpeg_start_image_text)
        val bounds = Rect().apply { paint.getTextBounds(message, 0, message.length, this) }
        val textX = backRect.left + (backRect.width() - bounds.width()) / 2
        val textY = backRect.top + logo.height + (backRect.height() - logo.height) / 2 - bounds.height() / 2
        canvas.drawText(message, textX, textY, paint)

        startBitmap = bitmap
        return bitmap
    }
    private var currentBitrate = 0 // Synced from adaptive calculation at stream start
    private var lastBitrateUpdate = 0L

    private fun handleBitrateUpdate(latency: Long) {
        val now = System.currentTimeMillis()
        if (now - lastBitrateUpdate < 500) return // Limit updates to 2x per second

        // Sync initial bitrate from encoder if not yet set
        if (currentBitrate == 0) return

        var newBitrate = currentBitrate

        if (latency > 100) { // Congestion detected (send took > 100ms; was 50ms, too aggressive for LAN)
            // Gentle backoff: Drop 15% or 500kbps, whichever is larger
            val drop = max(500000, (currentBitrate * 0.15).toInt())
            newBitrate = max(2000000, currentBitrate - drop) // Floor: 2Mbps (was 1Mbps)
            XLog.i(getLog("ABR", "Congestion! Latency=${latency}ms. Drop to ${newBitrate/1000}kbps"))
        } else if (latency < 15) { // Network is free
            // Fast recovery: Add 1Mbps (was 500kbps)
            if (currentBitrate < 20000000) {
                newBitrate = min(20000000, currentBitrate + 1000000)
            }
        }

        if (newBitrate != currentBitrate) {
            currentBitrate = newBitrate
            lastBitrateUpdate = now
            h264Encoder?.setBitrate(currentBitrate)
        }
    }
}
