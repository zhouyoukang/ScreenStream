package info.dvkr.screenstream.mjpeg.internal

import android.content.Context
import android.graphics.Bitmap
import android.os.Build
import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.flow.onEach
import okhttp3.*
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer
import java.security.SecureRandom
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/**
 * CloudRelayClient 鈥?鎵嬫満鑷富鍏綉鎶曞睆鏍稿績
 *
 * 鏀寔鍙屾ā寮忥細
 *   MJPEG: bitmapStateFlow 鈫?JPEG鍘嬬缉 鈫?type=3甯?鈫?relay 鈫?娴忚鍣?img>
 *   H264:  h264SharedFlow 鈫?type=0/1/2甯?鈫?relay 鈫?娴忚鍣╓ebCodecs
 *
 * 鐢ㄦ埛浣撻獙锛氬紑濮嬫姇灞?鈫?鑷姩杩瀝elay 鈫?閫氱煡鏍忔樉绀鸿鐪婾RL 鈫?杩滅▼娴忚鍣ㄦ墦寮€鍗崇湅+鎿嶆帶
 */
internal class CloudRelayClient(
    private val context: Context,
    private val h264Flow: Flow<H264Frame>?,
    private val bitmapFlow: StateFlow<Bitmap>?,
    private val jpegQuality: Int = 82,
    private val maxFps: Int = 25,
    private val inputPort: Int = 8084
) {
    companion object {
        const val FRAME_TYPE_JPEG: Byte = 3
        private const val RELAY_URL = "wss://aiotvr.xyz/relay/"
        private const val RELAY_TOKEN = "screenstream_2026"
        private const val VIEWER_BASE = "https://aiotvr.xyz/cast/"
        private const val MAX_RECONNECT_DELAY = 30_000L
        private const val INITIAL_RECONNECT_DELAY = 2_000L
    }

    // Public state
    val isConnected: Boolean get() = _connected.get()
    val roomCode: String get() = _roomCode.get()
    val viewerUrl: String get() = if (_roomCode.get().isNotEmpty())
        "$VIEWER_BASE?room=${_roomCode.get()}&token=$RELAY_TOKEN" else ""
    val viewerCount: Int get() = _viewerCount

    // Internal state
    private val _connected = AtomicBoolean(false)
    private val _roomCode = AtomicReference("")
    @Volatile private var _viewerCount = 0
    @Volatile private var _running = false
    private var webSocket: WebSocket? = null
    private var reconnectDelay = INITIAL_RECONNECT_DELAY
    private var frameJob: Job? = null
    private var reconnectJob: Job? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var onStateChanged: ((connected: Boolean, url: String, viewers: Int) -> Unit)? = null

    private val client = OkHttpClient.Builder()
        .pingInterval(25, TimeUnit.SECONDS)
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS) // No read timeout for WS
        .retryOnConnectionFailure(true)
        .build()

    fun setStateListener(listener: (connected: Boolean, url: String, viewers: Int) -> Unit) {
        onStateChanged = listener
    }

    fun start(customRoom: String? = null) {
        if (_running) return
        _running = true

        val room = customRoom ?: generateRoomCode()
        _roomCode.set(room)

        XLog.i(getLog("start", "Room: $room"))
        connect()
    }

    fun stop() {
        _running = false
        reconnectJob?.cancel()
        frameJob?.cancel()
        webSocket?.close(1000, "Streaming stopped")
        webSocket = null
        _connected.set(false)
        _viewerCount = 0
        _roomCode.set("")
        notifyState()
        XLog.i(getLog("stop", "CloudRelay stopped"))
    }

    fun destroy() {
        stop()
        scope.cancel()
        client.dispatcher.executorService.shutdown()
        client.connectionPool.evictAll()
    }

    private fun connect() {
        if (!_running) return

        val room = _roomCode.get()
        val deviceName = "${Build.MANUFACTURER} ${Build.MODEL}"
        val url = "$RELAY_URL?role=provider&token=$RELAY_TOKEN&room=$room&type=phone&device=$deviceName"

        XLog.d(getLog("connect", "Connecting to relay: room=$room"))

        val request = Request.Builder()
            .url(url)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                XLog.i(getLog("onOpen", "Connected to relay"))
                _connected.set(true)
                reconnectDelay = INITIAL_RECONNECT_DELAY

                // Send device info
                val deviceInfo = JSONObject().apply {
                    put("type", "device_info")
                    put("data", JSONObject().apply {
                        put("model", Build.MODEL)
                        put("manufacturer", Build.MANUFACTURER)
                        put("android", Build.VERSION.RELEASE)
                        put("sdk", Build.VERSION.SDK_INT)
                    })
                }
                webSocket.send(deviceInfo.toString())

                // Start frame forwarding
                startFrameForwarding(webSocket)
                notifyState()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val msg = JSONObject(text)
                    handleRelayMessage(msg)
                } catch (e: Exception) {
                    XLog.w(getLog("onMessage", "Parse error: ${e.message}"))
                }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                // Binary from viewer (unused for now)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                XLog.d(getLog("onClosing", "code=$code reason=$reason"))
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                XLog.i(getLog("onClosed", "code=$code reason=$reason"))
                _connected.set(false)
                _viewerCount = 0
                notifyState()
                scheduleReconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                XLog.w(getLog("onFailure", "Error: ${t.message}"))
                _connected.set(false)
                _viewerCount = 0
                notifyState()
                scheduleReconnect()
            }
        })
    }

    private fun startFrameForwarding(ws: WebSocket) {
        frameJob?.cancel()

        if (h264Flow != null) {
            // H264 mode: forward H264 frames directly
            frameJob = scope.launch {
                try {
                    h264Flow.onEach { frame ->
                        if (!_connected.get()) return@onEach
                        if (frame.type == H264Frame.TYPE_DELTA_FRAME && ws.queueSize() > 524288) return@onEach

                        val buffer = ByteBuffer.allocate(9 + frame.data.size)
                        buffer.put(frame.type.toByte())
                        buffer.putLong(frame.timestamp)
                        buffer.put(frame.data)
                        buffer.flip()
                        val bytes = ByteArray(buffer.remaining())
                        buffer.get(bytes)
                        ws.send(bytes.toByteString())
                    }.collect()
                } catch (_: CancellationException) {
                } catch (e: Exception) {
                    XLog.e(getLog("h264Forwarding", "Error"), e)
                }
            }
        } else if (bitmapFlow != null) {
            // MJPEG mode: compress bitmap to JPEG and send with type=3
            frameJob = scope.launch {
                val jpegOut = ByteArrayOutputStream()
                val frameInterval = 1000L / maxFps
                try {
                    while (isActive && _connected.get()) {
                        val bitmap = bitmapFlow.value
                        if (bitmap.width > 1 && bitmap.height > 1 && ws.queueSize() < 524288) {
                            jpegOut.reset()
                            bitmap.compress(Bitmap.CompressFormat.JPEG, jpegQuality, jpegOut)
                            val jpegData = jpegOut.toByteArray()
                            if (jpegData.isNotEmpty()) {
                                val buffer = ByteBuffer.allocate(9 + jpegData.size)
                                buffer.put(FRAME_TYPE_JPEG)
                                buffer.putLong(System.currentTimeMillis() * 1000)
                                buffer.put(jpegData)
                                buffer.flip()
                                val bytes = ByteArray(buffer.remaining())
                                buffer.get(bytes)
                                ws.send(bytes.toByteString())
                            }
                        }
                        delay(frameInterval)
                    }
                } catch (_: CancellationException) {
                } catch (e: Exception) {
                    XLog.e(getLog("mjpegForwarding", "Error"), e)
                }
            }
        }
    }

    private fun handleRelayMessage(msg: JSONObject) {
        when (msg.optString("type")) {
            "registered" -> {
                val data = msg.optJSONObject("data")
                val roomId = data?.optString("roomId") ?: ""
                val viewerUrl = data?.optString("viewerUrl") ?: ""
                XLog.i(getLog("registered", "Room=$roomId URL=$viewerUrl"))
            }

            "viewer_joined" -> {
                _viewerCount = msg.optJSONObject("data")?.optInt("count", 0) ?: 0
                XLog.i(getLog("viewer", "Joined. Total=$_viewerCount"))
                notifyState()
            }

            "viewer_left" -> {
                _viewerCount = msg.optJSONObject("data")?.optInt("count", 0) ?: 0
                XLog.i(getLog("viewer", "Left. Total=$_viewerCount"))
                notifyState()
            }

            // Touch/control commands from viewer 鈫?forward to InputService
            "touch" -> forwardToInput(msg)
            "key" -> forwardToInput(msg)
            "text" -> forwardToInput(msg)
            "scroll" -> forwardToInput(msg)
            "control" -> forwardToInput(msg)
            "api_call" -> forwardToInput(msg)

            "request_keyframe" -> {
                // The streaming service handles this via its own mechanism
                XLog.d(getLog("relay", "Keyframe requested"))
            }
        }
    }

    /**
     * Forward viewer control commands to InputService REST API on localhost.
     * Maps relay protocol 鈫?InputService endpoints (POST /tap, /swipe, /back, etc.)
     */
    private fun forwardToInput(msg: JSONObject) {
        scope.launch {
            try {
                val type = msg.optString("type")
                val data = msg.optJSONObject("data") ?: JSONObject()

                when (type) {
                    "touch" -> {
                        when (data.optString("action", "tap")) {
                            "tap" -> postInput("/tap", JSONObject().apply {
                                put("nx", data.optDouble("x", 0.5))
                                put("ny", data.optDouble("y", 0.5))
                            })
                            "swipe" -> postInput("/swipe", JSONObject().apply {
                                put("nx1", data.optDouble("fromX", 0.5))
                                put("ny1", data.optDouble("fromY", 0.5))
                                put("nx2", data.optDouble("toX", 0.5))
                                put("ny2", data.optDouble("toY", 0.5))
                                put("duration", data.optInt("duration", 300))
                            })
                            "longpress" -> postInput("/longpress", JSONObject().apply {
                                put("nx", data.optDouble("x", 0.5))
                                put("ny", data.optDouble("y", 0.5))
                                put("duration", data.optInt("duration", 800))
                            })
                            "doubletap" -> postInput("/doubletap", JSONObject().apply {
                                put("nx", data.optDouble("x", 0.5))
                                put("ny", data.optDouble("y", 0.5))
                            })
                        }
                    }
                    "scroll" -> postInput("/scroll", JSONObject().apply {
                        put("direction", if (data.optDouble("deltaY", 0.0) > 0) "down" else "up")
                        put("distance", 500)
                    })
                    "control" -> {
                        val action = data.optString("action", "")
                        if (action.isNotEmpty()) {
                            val endpoint = when (action) {
                                "volume_up" -> "/volume/up"
                                "volume_down" -> "/volume/down"
                                "power" -> "/power"
                                else -> "/$action"
                            }
                            postInput(endpoint, null)
                        }
                    }
                    "text" -> postInput("/text", JSONObject().apply {
                        put("text", data.optString("text", ""))
                    })
                    "key" -> postInput("/key", JSONObject().apply {
                        put("keyCode", data.optInt("keyCode", 0))
                    })
                }
            } catch (e: Exception) {
                XLog.w(getLog("forwardToInput", "Error: ${e.message}"))
            }
        }
    }

    /**
     * POST to InputService HTTP endpoint on localhost:8084.
     * Uses HttpURLConnection (zero extra deps).
     */
    private fun postInput(path: String, body: JSONObject?) {
        try {
            val url = URL("http://127.0.0.1:$inputPort$path")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 2000
            conn.readTimeout = 2000
            if (body != null) {
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                OutputStreamWriter(conn.outputStream).use { it.write(body.toString()) }
            }
            val code = conn.responseCode
            if (code !in 200..204) {
                XLog.w(getLog("postInput", "$path 鈫?HTTP $code"))
            }
            conn.disconnect()
        } catch (e: Exception) {
            XLog.v(getLog("postInput", "$path failed: ${e.message}"))
        }
    }

    private fun scheduleReconnect() {
        if (!_running) return

        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            XLog.d(getLog("reconnect", "Waiting ${reconnectDelay}ms"))
            delay(reconnectDelay)
            reconnectDelay = (reconnectDelay * 1.5).toLong().coerceAtMost(MAX_RECONNECT_DELAY)
            connect()
        }
    }

    private fun notifyState() {
        try {
            onStateChanged?.invoke(_connected.get(), viewerUrl, _viewerCount)
        } catch (e: Exception) {
            XLog.w(getLog("notifyState", "Error: ${e.message}"))
        }
    }

    private fun generateRoomCode(): String {
        val random = SecureRandom()
        return String.format("%06d", random.nextInt(1000000))
    }
}
