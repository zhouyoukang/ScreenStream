package info.dvkr.screenstream.mjpeg.internal

import android.content.Context
import android.content.pm.ApplicationInfo
import android.graphics.Bitmap
import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import info.dvkr.screenstream.common.getVersionName
import info.dvkr.screenstream.common.randomString
import info.dvkr.screenstream.mjpeg.R
import info.dvkr.screenstream.mjpeg.internal.HttpServerData.Companion.getClientId
import info.dvkr.screenstream.mjpeg.settings.MjpegSettings
import info.dvkr.screenstream.mjpeg.ui.MjpegError
import io.ktor.http.CacheControl
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpMethod
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.CachingOptions
import io.ktor.http.content.OutgoingContent
import io.ktor.server.application.Application
import io.ktor.server.application.ApplicationStarted
import io.ktor.server.application.ApplicationStopped
import io.ktor.server.application.install
import io.ktor.server.application.serverConfig
import io.ktor.server.routing.routing
import io.ktor.server.cio.CIO
import io.ktor.server.engine.EmbeddedServer
import io.ktor.server.engine.connector
import io.ktor.server.engine.embeddedServer
import io.ktor.server.plugins.cachingheaders.CachingHeaders
import io.ktor.server.plugins.compression.Compression
import io.ktor.server.plugins.compression.deflate
import io.ktor.server.plugins.compression.gzip
import io.ktor.server.plugins.cors.routing.CORS
import io.ktor.server.plugins.defaultheaders.DefaultHeaders
import io.ktor.server.plugins.forwardedheaders.ForwardedHeaders
import io.ktor.server.plugins.origin
import io.ktor.server.plugins.statuspages.StatusPages
import io.ktor.server.response.respond
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.get
import info.dvkr.screenstream.input.installInputRoutes
import io.ktor.server.websocket.WebSockets
import io.ktor.server.websocket.webSocket
import io.ktor.utils.io.ByteWriteChannel
import io.ktor.utils.io.core.buildPacket
import io.ktor.utils.io.core.writeFully
import io.ktor.utils.io.writeFully
import io.ktor.server.websocket.DefaultWebSocketServerSession
import io.ktor.websocket.DefaultWebSocketSession
import io.ktor.websocket.Frame
import io.ktor.websocket.readText
import io.ktor.websocket.send
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import java.nio.ByteBuffer
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.flow.shareIn
import kotlinx.coroutines.flow.takeWhile
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.io.readByteArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.BindException
import java.net.SocketException
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

internal class HttpServer(
    context: Context,
    private val mjpegSettings: MjpegSettings,
    private val bitmapStateFlow: StateFlow<Bitmap>,
    private val h264SharedFlow: Flow<H264Frame>?,
    private val h265SharedFlow: Flow<H264Frame>?,
    private val audioFlow: Flow<ByteArray>?,
    private val sendEvent: (MjpegEvent) -> Unit,
    private val requestKeyFrame: () -> Unit
) {
    private data class SettingsSnapshot(
        val enableButtons: Boolean,
        val backColor: String,
        val fitWindow: Boolean,
        val streamCodec: Int,
    )

    private val debuggable = context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0
    private val favicon: ByteArray = context.getFileFromAssets("favicon.ico")
    private val logoSvg: ByteArray = context.getFileFromAssets("logo.svg")
    private val jmuxerJs: ByteArray = context.getFileFromAssets("jmuxer.min.js")
    private val baseIndexHtml = String(context.getFileFromAssets("index.html"), StandardCharsets.UTF_8)
        .replace("%CONNECTING%", context.getString(R.string.mjpeg_html_stream_connecting))
        .replace("%STREAM_REQUIRE_PIN%", context.getString(R.string.mjpeg_html_stream_require_pin))
        .replace("%ENTER_PIN%", context.getString(R.string.mjpeg_html_enter_pin))
        .replace("%SUBMIT_PIN%", context.getString(R.string.mjpeg_html_submit_pin))
        .replace("%WRONG_PIN_MESSAGE%", context.getString(R.string.mjpeg_html_wrong_pin))
        .replace("%ADDRESS_BLOCKED%", context.getString(R.string.mjpeg_html_address_blocked))
        .replace("%ERROR%", context.getString(R.string.mjpeg_html_error_unspecified)) //TODO not used
        .replace("%DD_SERVICE%", if (debuggable) "mjpeg_client:dev" else "mjpeg_client:prod")
        .replace("DD_HANDLER", if (debuggable) "[\"http\", \"console\"]" else "[\"http\"]")
        .replace("%APP_VERSION%", context.getVersionName())

    private val indexHtml: AtomicReference<String> = AtomicReference("")
    private val lastJPEG: AtomicReference<ByteArray> = AtomicReference(ByteArray(0))
    private val serverData: HttpServerData = HttpServerData(sendEvent)
    private val mjpegSharedFlow: AtomicReference<SharedFlow<ByteArray>> = AtomicReference(null)
    private val ktorServer: AtomicReference<Pair<EmbeddedServer<*, *>, CompletableDeferred<Unit>>> = AtomicReference(null)

    init {
        XLog.d(getLog("init"))
    }

    internal suspend fun start(serverAddresses: List<MjpegNetInterface>) {
        XLog.d(getLog("startServer"))

        serverData.configure(mjpegSettings)

        val coroutineScope = CoroutineScope(Job() + Dispatchers.Default)

        mjpegSettings.data
            .map { Pair(it.htmlBackColor, it.htmlFitWindow) }
            .distinctUntilChanged()
            .onEach { (backColor, fitWindow) ->
                indexHtml.set(
                    baseIndexHtml
                        .replace("BACKGROUND_COLOR", backColor.toColorHexString())
                        .replace("FIT_WINDOW", if (fitWindow) """style='width: 100%; object-fit: contain;'""" else "")
                )
            }
            .launchIn(coroutineScope)

        mjpegSettings.data
            .map {
                SettingsSnapshot(
                    enableButtons = it.htmlEnableButtons && serverData.enablePin.not(),
                    backColor = it.htmlBackColor.toColorHexString(),
                    fitWindow = it.htmlFitWindow,
                    streamCodec = it.streamCodec
                )
            }
            .distinctUntilChanged()
            .onEach { (enableButtons, backColor, fitWindow, streamCodec) ->
                val data = JSONObject(
                    mapOf(
                        "enableButtons" to enableButtons,
                        "backColor" to backColor,
                        "fitWindow" to fitWindow,
                        "streamCodec" to streamCodec
                    )
                )
                serverData.notifyClients("SETTINGS", data)
            }
            .launchIn(coroutineScope)

        val resultJpegStream = ByteArrayOutputStream()
        lastJPEG.set(ByteArray(0))

        @OptIn(ExperimentalCoroutinesApi::class)
        val mjpegFlow = combine(bitmapStateFlow, mjpegSettings.data) { bitmap, settings -> bitmap to settings }
            .conflate()
            .map { (bitmap, settings) ->
                withContext(Dispatchers.IO) {
                    resultJpegStream.reset()
                    bitmap.compress(Bitmap.CompressFormat.JPEG, settings.jpegQuality, resultJpegStream)
                    resultJpegStream.toByteArray() to settings.maxFPS
                }
            }
            .filter { (jpeg, _) -> jpeg.isNotEmpty() }
            .onEach { (jpeg, _) -> lastJPEG.set(jpeg) }
            .flatMapLatest { (jpeg, maxFPS) ->
                if (maxFPS > 0) { // If maxFPS > 0, repeatedly emit the same JPEG every second (keep-alive)
                    flow {
                        while (currentCoroutineContext().isActive) {
                            emit(jpeg)
                            delay(1000)
                        }
                    }
                } else {
                    flowOf(jpeg)
                }
            }
            .conflate()
            .shareIn(coroutineScope, SharingStarted.Eagerly, 1)

        mjpegSharedFlow.set(mjpegFlow)

        val serverPort = mjpegSettings.data.value.serverPort
        val server = embeddedServer(
            factory = CIO,
            rootConfig = serverConfig {
                parentCoroutineContext = CoroutineExceptionHandler { _, throwable ->
                    if (throwable is BindException) return@CoroutineExceptionHandler
                    if (throwable is SocketException) return@CoroutineExceptionHandler
                    XLog.i(this@HttpServer.getLog("parentCoroutineContext", "coroutineExceptionHandler: $throwable"), throwable)
                }
                module { appModule() }
            },
            configure = {
                connectionIdleTimeoutSeconds = 60
                reuseAddress = true
                shutdownGracePeriod = 0
                shutdownTimeout = 500
                // HTTP connector
                connector {
                    host = "0.0.0.0"
                    port = serverPort
                }
            }
        )

        ktorServer.set(server to CompletableDeferred())

        server.monitor.subscribe(ApplicationStarted) {
            XLog.i(getLog("monitor", "KtorStarted: ${it.hashCode()}"))
        }

        server.monitor.subscribe(ApplicationStopped) {
            XLog.i(getLog("monitor", "KtorStopped: ${it.hashCode()}"))
            coroutineScope.cancel()
            serverData.clear()
            ktorServer.get()?.second?.complete(Unit)
        }

        try {
            server.start(false)
        } catch (cause: CancellationException) {
            if (cause.cause is SocketException) {
                XLog.w(getLog("startServer.CancellationException.SocketException", cause.cause.toString()))
                sendEvent(MjpegStreamingService.InternalEvent.Error(MjpegError.AddressInUseException))
            } else {
                XLog.w(getLog("startServer.CancellationException", cause.toString()), cause)
                sendEvent(MjpegStreamingService.InternalEvent.Error(MjpegError.HttpServerException))
            }
        } catch (cause: BindException) {
            XLog.w(getLog("startServer.BindException", cause.toString()))
            sendEvent(MjpegStreamingService.InternalEvent.Error(MjpegError.AddressInUseException))
        } catch (cause: Throwable) {
            XLog.e(getLog("startServer.Throwable"), cause)
            sendEvent(MjpegStreamingService.InternalEvent.Error(MjpegError.HttpServerException))
        }
        XLog.d(getLog("startServer", "Done. Ktor: ${server.hashCode()} "))
    }

    internal suspend fun stop(reloadClients: Boolean) = coroutineScope {
        XLog.d(getLog("stopServer", "reloadClients: $reloadClients"))
        launch(Dispatchers.Default) {
            ktorServer.getAndSet(null)?.let { (server, stopJob) ->
                if (stopJob.isActive) {
                    if (reloadClients) serverData.notifyClients("RELOAD", timeout = 250)
                    val hashCode = server.hashCode()
                    XLog.i(this@HttpServer.getLog("stopServer", "Ktor: $hashCode"))
                    server.stop(250, 500, TimeUnit.MILLISECONDS)
                    XLog.i(this@HttpServer.getLog("stopServer", "Done. Ktor: $hashCode"))
                }
            }
            mjpegSharedFlow.set(null)
            XLog.d(this@HttpServer.getLog("stopServer", "Done"))
        }
    }

    internal suspend fun destroy() {
        XLog.d(getLog("destroy"))
        serverData.destroy()
        stop(false)
    }

    private suspend fun DefaultWebSocketSession.send(type: String, data: Any?) {
        if (isActive) send(JSONObject().put("type", type).apply { if (data != null) put("data", data) }.toString())
    }

    private suspend fun DefaultWebSocketServerSession.handleVideoStream(
        codec: String,
        videoFlow: Flow<H264Frame>?,
        reportLatency: Boolean
    ) {
        val clientId = call.request.getClientId()
        XLog.d(getLog(codec, "Connected: $clientId"))
        requestKeyFrame()
        var lastReport = 0L
        try {
            videoFlow?.collect { frame ->
                val buffer = ByteBuffer.allocate(9 + frame.data.size)
                buffer.put(frame.type.toByte())
                buffer.putLong(frame.timestamp)
                buffer.put(frame.data)
                buffer.flip()

                if (reportLatency) {
                    val start = System.currentTimeMillis()
                    send(Frame.Binary(true, buffer))
                    val end = System.currentTimeMillis()
                    val latency = end - start
                    if (latency > 30 || (end - lastReport > 500)) {
                        sendEvent(MjpegStreamingService.InternalEvent.UpdateBitrate(latency))
                        lastReport = end
                    }
                } else {
                    send(Frame.Binary(true, buffer))
                }
            }
        } catch (e: ClosedReceiveChannelException) {
            XLog.d(getLog(codec, "Disconnected: $clientId"))
        } catch (e: Exception) {
            XLog.e(getLog(codec, "Error"), e)
        }
    }

    private fun Application.appModule() {
        val crlf = "\r\n".toByteArray()
        val jpegBaseHeader = "Content-Type: image/jpeg\r\nContent-Length: ".toByteArray()
        val multipartBoundary = randomString(20)
        val contentType = ContentType.parse("multipart/x-mixed-replace; boundary=$multipartBoundary")
        val jpegBoundary = "--$multipartBoundary\r\n".toByteArray()

        install(Compression) {
            gzip()
            deflate()
        }
        install(WebSockets) {
            pingPeriodMillis = 45000
            timeoutMillis = 45000 // 45 seconds for FRP
        }
        install(CachingHeaders) { options { _, _ -> CachingOptions(CacheControl.NoStore(CacheControl.Visibility.Private)) } }
        install(DefaultHeaders)
        install(ForwardedHeaders)
        install(CORS) {
            anyHost()
            allowMethod(HttpMethod.Get)
            allowMethod(HttpMethod.Head)
            allowMethod(HttpMethod.Options)
            allowHeader(HttpHeaders.ContentType)
            allowHeader(HttpHeaders.Range)
            allowNonSimpleContentTypes = true

            exposeHeader(HttpHeaders.ContentLength)
            exposeHeader(HttpHeaders.ContentRange)
            exposeHeader(HttpHeaders.ContentType)
        }
        install(StatusPages) {
            exception<Throwable> { call, cause ->
                if (cause is IOException || cause is IllegalArgumentException || cause is IllegalStateException) return@exception
                XLog.e(this@appModule.getLog("exception"), RuntimeException("Throwable", cause))
                sendEvent(MjpegStreamingService.InternalEvent.Error(MjpegError.HttpServerException))
                call.respondText(text = "500: Internal Server Error", status = HttpStatusCode.InternalServerError)
            }
        }

        routing {
            get("/") {
                call.response.headers.append(HttpHeaders.CacheControl, "no-store, no-cache, must-revalidate, max-age=0")
                call.respondText(indexHtml.get(), ContentType.Text.Html)
            }
            get("favicon.ico") { call.respondBytes(favicon, ContentType.Image.XIcon) }
            get("logo.svg") { call.respondBytes(logoSvg, ContentType.Image.SVG) }
            get("jmuxer.min.js") { call.respondBytes(jmuxerJs, ContentType.parse("application/javascript")) }
            get("start-stop") {
                if (mjpegSettings.data.value.htmlEnableButtons && serverData.enablePin.not())
                    sendEvent(MjpegStreamingService.InternalEvent.StartStopFromWebPage)
                call.respond(HttpStatusCode.NoContent)
            }

            installInputRoutes()

            get(serverData.jpegFallbackAddress) {
                if (serverData.isAddressBlocked(call.request.origin.remoteAddress)) call.respond(HttpStatusCode.Forbidden)
                else {
                    val clientId = call.request.queryParameters["clientId"] ?: "-"
                    val remoteAddress = call.request.origin.remoteAddress
                    val remotePort = call.request.origin.remotePort
                    serverData.addConnected(clientId, remoteAddress, remotePort)
                    val bytes = lastJPEG.get()
                    call.respondBytes(bytes, ContentType.Image.JPEG)
                    serverData.setNextBytes(clientId, remoteAddress, remotePort, bytes.size)
                    serverData.setDisconnected(clientId, remoteAddress, remotePort)
                }
            }

            webSocket("/socket") {
                val clientId = call.request.getClientId()
                val remoteAddress = call.request.origin.remoteAddress
                serverData.addClient(clientId, this)

                try {
                    for (frame in incoming) {
                        frame as? Frame.Text ?: continue
                        val msg = runCatching { JSONObject(frame.readText()) }.getOrNull() ?: continue

                        val enableButtons = mjpegSettings.data.value.htmlEnableButtons && serverData.enablePin.not()
                        val streamData = JSONObject()
                            .put("enableButtons", enableButtons)
                            .put("streamAddress", serverData.streamAddress)
                            .put("streamCodec", mjpegSettings.data.value.streamCodec)

                        when (val type = msg.optString("type").uppercase()) {
                            "HEARTBEAT" -> send("HEARTBEAT", msg.optString("data"))

                            "CONNECT" -> when {
                                mjpegSettings.data.value.enablePin.not() -> send("STREAM_ADDRESS", streamData)
                                serverData.isAddressBlocked(remoteAddress) -> send("UNAUTHORIZED", "ADDRESS_BLOCKED")
                                serverData.isClientAuthorized(clientId) -> send("STREAM_ADDRESS", streamData)
                                else -> send("UNAUTHORIZED", null)
                            }

                            "PIN" -> when {
                                serverData.isPinValid(clientId, remoteAddress, msg.optString("data")) -> send("STREAM_ADDRESS", streamData)
                                serverData.isAddressBlocked(remoteAddress) -> send("UNAUTHORIZED", "ADDRESS_BLOCKED")
                                else -> send("UNAUTHORIZED", "WRONG_PIN")
                            }

                            else -> {
                                val m = "Unknown message type: $type"
                                XLog.e(this@appModule.getLog("socket", m), IllegalArgumentException(m))
                            }
                        }
                    }
                } catch (ignore: CancellationException) {
                } catch (cause: Exception) {
                    XLog.w(this@appModule.getLog("socket", "catch: ${cause.localizedMessage}"), cause)
                } finally {
                    XLog.i(this@appModule.getLog("socket", "finally: $clientId"))
                    serverData.removeSocket(clientId)
                }
            }

            webSocket("/stream/h264") { handleVideoStream("H264", h264SharedFlow, reportLatency = true) }
            webSocket("/stream/h265") { handleVideoStream("H265", h265SharedFlow, reportLatency = false) }

            webSocket("/stream/audio") {
                val clientId = call.request.getClientId()
                XLog.d(this@appModule.getLog("Audio", "Connected: $clientId"))
                try {
                    audioFlow?.collect { chunk ->
                        send(Frame.Binary(true, chunk))
                    }
                } catch (e: ClosedReceiveChannelException) {
                    XLog.d(this@appModule.getLog("Audio", "Disconnected: $clientId"))
                } catch (e: Exception) {
                    XLog.e(this@appModule.getLog("Audio", "Error"), e)
                }
            }
        }
    }
}
