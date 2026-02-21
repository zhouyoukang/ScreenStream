package info.dvkr.screenstream.input.api

import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.engine.*
import io.ktor.server.netty.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

@Serializable
data class TouchEvent(
    val x: Int,
    val y: Int,
    val action: String = "tap", // tap, press, release, move
    val pressure: Float = 1.0f,
    val duration: Long = 100
)

@Serializable
data class KeyEvent(
    val keyCode: Int,
    val action: String = "press", // press, release, longpress
    val metaState: Int = 0
)

@Serializable
data class TextEvent(
    val text: String,
    val append: Boolean = false
)

@Serializable
data class GestureEvent(
    val type: String, // scroll, swipe, pinch, rotate
    val startX: Int,
    val startY: Int,
    val endX: Int,
    val endY: Int,
    val duration: Long = 500
)

@Serializable
data class InputConfig(
    val enableTouch: Boolean = true,
    val enableKeyboard: Boolean = true,
    val enableGesture: Boolean = true,
    val maxLatency: Long = 100,
    val requireAuth: Boolean = false
)

@Serializable
data class InputStatus(
    val isActive: Boolean,
    val eventsProcessed: Long,
    val averageLatency: Double,
    val lastEventTime: Long?,
    val config: InputConfig
)

/**
 * 反向控制API独立版本
 * 提供触摸、按键、手势等输入事件的RESTful API接口
 */
class InputApiServer {
    private val json = Json { ignoreUnknownKeys = true }
    private var server: NettyApplicationEngine? = null
    private val isRunning = AtomicBoolean(false)
    private val eventsProcessed = AtomicLong(0)
    private val totalLatency = AtomicLong(0)
    private var lastEventTime: Long? = null
    private var currentConfig = InputConfig()
    
    fun start(port: Int = 8084) {
        if (isRunning.get()) {
            println("Input API Server already running on port $port")
            return
        }
        
        server = embeddedServer(Netty, port = port, host = "0.0.0.0") {
            configureRouting()
        }.start(wait = false)
        
        isRunning.set(true)
        println("Input API Server started on port $port")
    }
    
    fun stop() {
        server?.stop(1000, 5000)
        isRunning.set(false)
        println("Input API Server stopped")
    }
    
    private fun processEvent(eventType: String): Map<String, Any> {
        val startTime = System.currentTimeMillis()
        
        // 模拟事件处理延迟
        Thread.sleep(10)
        
        val endTime = System.currentTimeMillis()
        val latency = endTime - startTime
        
        eventsProcessed.incrementAndGet()
        totalLatency.addAndGet(latency)
        lastEventTime = endTime
        
        return mapOf(
            "success" to true,
            "eventType" to eventType,
            "latency" to latency,
            "timestamp" to endTime
        )
    }
    
    private fun getCurrentStatus(): InputStatus {
        val processed = eventsProcessed.get()
        val avgLatency = if (processed > 0) {
            totalLatency.get().toDouble() / processed
        } else {
            0.0
        }
        
        return InputStatus(
            isActive = isRunning.get(),
            eventsProcessed = processed,
            averageLatency = avgLatency,
            lastEventTime = lastEventTime,
            config = currentConfig
        )
    }
    
    private fun Application.configureRouting() {
        routing {
            get("/health") {
                call.respond(HttpStatusCode.OK, mapOf("status" to "healthy", "service" to "Input"))
            }
            
            get("/status") {
                call.respond(HttpStatusCode.OK, getCurrentStatus())
            }
            
            post("/start") {
                try {
                    val config = if (call.request.contentLength() != null && call.request.contentLength()!! > 0) {
                        json.decodeFromString<InputConfig>(call.receiveText())
                    } else {
                        InputConfig()
                    }
                    
                    currentConfig = config
                    
                    call.respond(HttpStatusCode.OK, mapOf(
                        "success" to true,
                        "message" to "Input service started",
                        "config" to config
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Failed to start input service: ${e.message}"
                    ))
                }
            }
            
            post("/stop") {
                call.respond(HttpStatusCode.OK, mapOf(
                    "success" to true,
                    "message" to "Input service stopped"
                ))
            }
            
            // 触摸事件
            post("/touch") {
                if (!currentConfig.enableTouch) {
                    call.respond(HttpStatusCode.Forbidden, mapOf(
                        "success" to false,
                        "message" to "Touch input disabled"
                    ))
                    return@post
                }
                
                try {
                    val touchEvent = json.decodeFromString<TouchEvent>(call.receiveText())
                    val result = processEvent("touch")
                    
                    call.respond(HttpStatusCode.OK, result + mapOf(
                        "event" to touchEvent,
                        "message" to "Touch event processed: ${touchEvent.action} at (${touchEvent.x}, ${touchEvent.y})"
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Invalid touch event: ${e.message}"
                    ))
                }
            }
            
            // 按键事件
            post("/key") {
                if (!currentConfig.enableKeyboard) {
                    call.respond(HttpStatusCode.Forbidden, mapOf(
                        "success" to false,
                        "message" to "Keyboard input disabled"
                    ))
                    return@post
                }
                
                try {
                    val keyEvent = json.decodeFromString<KeyEvent>(call.receiveText())
                    val result = processEvent("key")
                    
                    call.respond(HttpStatusCode.OK, result + mapOf(
                        "event" to keyEvent,
                        "message" to "Key event processed: ${keyEvent.action} keyCode ${keyEvent.keyCode}"
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Invalid key event: ${e.message}"
                    ))
                }
            }
            
            // 文本输入
            post("/text") {
                if (!currentConfig.enableKeyboard) {
                    call.respond(HttpStatusCode.Forbidden, mapOf(
                        "success" to false,
                        "message" to "Text input disabled"
                    ))
                    return@post
                }
                
                try {
                    val textEvent = json.decodeFromString<TextEvent>(call.receiveText())
                    val result = processEvent("text")
                    
                    call.respond(HttpStatusCode.OK, result + mapOf(
                        "event" to textEvent,
                        "message" to "Text input processed: '${textEvent.text}'"
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Invalid text event: ${e.message}"
                    ))
                }
            }
            
            // 手势事件
            post("/gesture") {
                if (!currentConfig.enableGesture) {
                    call.respond(HttpStatusCode.Forbidden, mapOf(
                        "success" to false,
                        "message" to "Gesture input disabled"
                    ))
                    return@post
                }
                
                try {
                    val gestureEvent = json.decodeFromString<GestureEvent>(call.receiveText())
                    val result = processEvent("gesture")
                    
                    call.respond(HttpStatusCode.OK, result + mapOf(
                        "event" to gestureEvent,
                        "message" to "Gesture processed: ${gestureEvent.type} from (${gestureEvent.startX}, ${gestureEvent.startY}) to (${gestureEvent.endX}, ${gestureEvent.endY})"
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Invalid gesture event: ${e.message}"
                    ))
                }
            }
            
            get("/config") {
                call.respond(HttpStatusCode.OK, currentConfig)
            }
            
            post("/config") {
                try {
                    val config = json.decodeFromString<InputConfig>(call.receiveText())
                    currentConfig = config
                    call.respond(HttpStatusCode.OK, mapOf(
                        "success" to true,
                        "config" to config
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Invalid config: ${e.message}"
                    ))
                }
            }
            
            // 重置统计
            post("/reset") {
                eventsProcessed.set(0)
                totalLatency.set(0)
                lastEventTime = null
                
                call.respond(HttpStatusCode.OK, mapOf(
                    "success" to true,
                    "message" to "Statistics reset"
                ))
            }
        }
    }
}

fun main() {
    val server = InputApiServer()
    server.start(8084)
    Runtime.getRuntime().addShutdownHook(Thread { server.stop() })
    Thread.currentThread().join()
}
