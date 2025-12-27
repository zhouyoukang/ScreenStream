package info.dvkr.screenstream.input

import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*
import io.ktor.server.application.*
import io.ktor.server.cio.*
import io.ktor.server.engine.*
import io.ktor.server.plugins.contentnegotiation.*
import io.ktor.server.plugins.cors.routing.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import io.ktor.http.ContentType
import kotlinx.serialization.Serializable

/**
 * HTTP API Server for remote input control
 * 
 * Provides REST endpoints for tap, swipe, key, and text input
 */
public class InputHttpServer(
    private val port: Int = 8086
) {
    private var server: EmbeddedServer<CIOApplicationEngine, CIOApplicationEngine.Configuration>? = null
    private val scope = CoroutineScope(Dispatchers.IO)

    // ==================== Request DTOs ====================

    @Serializable
    public data class TapRequest(val x: Int, val y: Int)

    @Serializable
    public data class SwipeRequest(
        val x1: Int,
        val y1: Int,
        val x2: Int,
        val y2: Int,
        val duration: Long = 300
    )

    @Serializable
    public data class KeyRequest(
        val keysym: Long,
        val down: Boolean = true
    )

    @Serializable
    public data class TextRequest(val text: String)

    @Serializable
    public data class PointerRequest(
        val buttonMask: Int,
        val x: Int,
        val y: Int
    )

    @Serializable
    public data class StatusResponse(
        val connected: Boolean,
        val inputEnabled: Boolean,
        val scaling: Float
    )

    @Serializable
    public data class OkResponse(val ok: Boolean = true)

    @Serializable
    public data class ErrorResponse(val error: String)

    // ==================== Server Lifecycle ====================

    public fun start() {
        if (server != null) {
            XLog.w(getLog("InputHttpServer", "Server already running"))
            return
        }

        scope.launch {
            try {
                server = embeddedServer(CIO, port = port) {
                    install(ContentNegotiation) {
                        json()
                    }
                    install(CORS) {
                        anyHost()
                        allowHeader(HttpHeaders.ContentType)
                        allowHeader(HttpHeaders.Accept)
                        allowHeader(HttpHeaders.Origin)
                        allowHeader(HttpHeaders.AccessControlRequestMethod)
                        allowHeader(HttpHeaders.AccessControlRequestHeaders)
                        allowMethod(HttpMethod.Post)
                        allowMethod(HttpMethod.Get)
                        allowMethod(HttpMethod.Options)
                        allowNonSimpleContentTypes = true
                    }
                    configureRouting()
                }.start(wait = false)

                XLog.i(getLog("InputHttpServer", "Started on port $port"))
            } catch (e: Exception) {
                XLog.e(getLog("InputHttpServer", "Failed to start: ${e.message}"))
            }
        }
    }

    public fun stop() {
        server?.stop(1000, 2000)
        server = null
        XLog.i(getLog("InputHttpServer", "Stopped"))
    }

    public fun isRunning(): Boolean = server != null

    // ==================== Routing ====================

    private fun Application.configureRouting() {
        routing {
            // Status endpoint
            get("/status") {
                val isConnected = InputService.isConnected()
                val isEnabled = InputService.isInputEnabled
                val scaling = InputService.scaling
                val json = "{\"connected\": $isConnected, \"inputEnabled\": $isEnabled, \"scaling\": $scaling}"
                call.respondText(json, ContentType.Application.Json)
            }

            // Tap at coordinates
            post("/tap") {
                val inputService = InputService.instance
                if (inputService == null) {
                    call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                    return@post
                }

                try {
                    val text = call.receiveText()
                    val json = JSONObject(text)
                    if (json.has("nx") && json.has("ny")) {
                        val nx = json.getDouble("nx").toFloat()
                        val ny = json.getDouble("ny").toFloat()
                        inputService.tapNormalized(nx, ny)
                    } else {
                        val x = json.getInt("x")
                        val y = json.getInt("y")
                        inputService.tap(x, y)
                    }
                    call.respondText("{\"ok\": true}", ContentType.Application.Json)
                } catch (e: Exception) {
                    call.respondText("{\"error\": \"${e.message}\"}", ContentType.Application.Json, HttpStatusCode.BadRequest)
                }
            }

            // Swipe gesture
            post("/swipe") {
                val inputService = InputService.instance
                if (inputService == null) {
                    call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                    return@post
                }

                try {
                    val text = call.receiveText()
                    val json = JSONObject(text)
                    val duration = json.optLong("duration", 300)
                    
                    if (json.has("nx1") && json.has("ny1") && json.has("nx2") && json.has("ny2")) {
                        val nx1 = json.getDouble("nx1").toFloat()
                        val ny1 = json.getDouble("ny1").toFloat()
                        val nx2 = json.getDouble("nx2").toFloat()
                        val ny2 = json.getDouble("ny2").toFloat()
                        inputService.swipeNormalized(nx1, ny1, nx2, ny2, duration)
                    } else {
                        val x1 = json.getInt("x1")
                        val y1 = json.getInt("y1")
                        val x2 = json.getInt("x2")
                        val y2 = json.getInt("y2")
                        inputService.swipe(x1, y1, x2, y2, duration)
                    }
                    call.respondText("{\"ok\": true}", ContentType.Application.Json)
                } catch (e: Exception) {
                    call.respondText("{\"error\": \"${e.message}\"}", ContentType.Application.Json, HttpStatusCode.BadRequest)
                }
            }

            // Key event
            post("/key") {
                val inputService = InputService.instance
                if (inputService == null) {
                    call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                    return@post
                }

                try {
                    val text = call.receiveText()
                    val json = JSONObject(text)
                    val keysym = json.getLong("keysym")
                    val down = json.optBoolean("down", true)
                    inputService.onKeyEvent(down, keysym)
                    call.respondText("{\"ok\": true}", ContentType.Application.Json)
                } catch (e: Exception) {
                    call.respondText("{\"error\": \"${e.message}\"}", ContentType.Application.Json, HttpStatusCode.BadRequest)
                }
            }

            // Text input
            post("/text") {
                val inputService = InputService.instance
                if (inputService == null) {
                    call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                    return@post
                }

                try {
                    val text = call.receiveText()
                    val json = JSONObject(text)
                    val input = json.getString("text")
                    inputService.inputText(input)
                    call.respondText("{\"ok\": true}", ContentType.Application.Json)
                } catch (e: Exception) {
                    call.respondText("{\"error\": \"${e.message}\"}", ContentType.Application.Json, HttpStatusCode.BadRequest)
                }
            }

            // Raw pointer event (VNC-style)
            post("/pointer") {
                val inputService = InputService.instance
                if (inputService == null) {
                    call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                    return@post
                }

                try {
                    val text = call.receiveText()
                    val json = JSONObject(text)
                    val buttonMask = json.getInt("buttonMask")
                    val x = json.getInt("x")
                    val y = json.getInt("y")
                    inputService.onPointerEvent(buttonMask, x, y)
                    call.respondText("{\"ok\": true}", ContentType.Application.Json)
                } catch (e: Exception) {
                    call.respondText("{\"error\": \"${e.message}\"}", ContentType.Application.Json, HttpStatusCode.BadRequest)
                }
            }

            // Navigation shortcuts
            post("/home") {
                InputService.instance?.goHome()
                    ?: return@post call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                call.respondText("{\"ok\": true}", ContentType.Application.Json)
            }

            post("/back") {
                InputService.instance?.goBack()
                    ?: return@post call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                call.respondText("{\"ok\": true}", ContentType.Application.Json)
            }

            post("/recents") {
                InputService.instance?.showRecents()
                    ?: return@post call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                call.respondText("{\"ok\": true}", ContentType.Application.Json)
            }

            post("/notifications") {
                InputService.instance?.showNotifications()
                    ?: return@post call.respondText("{\"error\": \"InputService not connected\"}", ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                call.respondText("{\"ok\": true}", ContentType.Application.Json)
            }

            // Set scaling factor
            post("/scaling/{factor}") {
                val factor = call.parameters["factor"]?.toFloatOrNull()
                if (factor == null || factor <= 0) {
                    call.respondText("{\"error\": \"Invalid scaling factor\"}", ContentType.Application.Json, HttpStatusCode.BadRequest)
                    return@post
                }
                InputService.scaling = factor
                call.respondText("{\"ok\": true}", ContentType.Application.Json)
            }

            // Enable/disable input
            post("/enable/{enabled}") {
                val enabled = call.parameters["enabled"]?.toBooleanStrictOrNull()
                if (enabled == null) {
                    call.respondText("{\"error\": \"Invalid enabled value\"}", ContentType.Application.Json, HttpStatusCode.BadRequest)
                    return@post
                }
                InputService.isInputEnabled = enabled
                call.respondText("{\"ok\": true}", ContentType.Application.Json)
            }
        }
    }
}
