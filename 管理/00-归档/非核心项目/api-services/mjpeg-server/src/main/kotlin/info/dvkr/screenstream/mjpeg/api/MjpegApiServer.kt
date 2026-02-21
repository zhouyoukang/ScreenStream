package info.dvkr.screenstream.mjpeg.api

import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.engine.*
import io.ktor.server.netty.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import kotlinx.coroutines.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

@Serializable
data class StreamConfig(
    val quality: String = "high",
    val fps: Int = 30,
    val resolution: String = "1080p",
    val autoStart: Boolean = true
)

@Serializable
data class StreamStatus(
    val isStreaming: Boolean,
    val connectedClients: Int,
    val fps: Int,
    val resolution: String,
    val startTime: Long?
)

@Serializable
data class ApiResponse<T>(
    val success: Boolean,
    val data: T? = null,
    val message: String? = null,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * MJPEG HTTP服务API独立版本
 * 提供RESTful API接口，方便后端直接测试而不需APK打包
 */
class MjpegApiServer {
    private val json = Json { ignoreUnknownKeys = true }
    private var server: NettyApplicationEngine? = null
    private val isRunning = AtomicBoolean(false)
    private val currentConfig = AtomicReference(StreamConfig())
    private val streamStatus = AtomicReference(StreamStatus(false, 0, 0, "1080p", null))
    
    fun start(port: Int = 8081) {
        if (isRunning.get()) {
            println("MJPEG API Server already running on port $port")
            return
        }
        
        server = embeddedServer(Netty, port = port, host = "0.0.0.0") {
            configureRouting()
        }.start(wait = false)
        
        isRunning.set(true)
        println("MJPEG API Server started on port $port")
    }
    
    fun stop() {
        server?.stop(1000, 5000)
        isRunning.set(false)
        println("MJPEG API Server stopped")
    }
    
    private fun Application.configureRouting() {
        routing {
            get("/health") {
                call.respond(HttpStatusCode.OK, ApiResponse(true, mapOf("status" to "healthy")))
            }
            
            get("/status") {
                val status = streamStatus.get()
                call.respond(HttpStatusCode.OK, ApiResponse(true, status))
            }
            
            post("/start") {
                try {
                    val config = if (call.request.contentLength() != null && call.request.contentLength()!! > 0) {
                        json.decodeFromString<StreamConfig>(call.receiveText())
                    } else {
                        StreamConfig()
                    }
                    
                    currentConfig.set(config)
                    val startTime = System.currentTimeMillis()
                    streamStatus.set(StreamStatus(
                        isStreaming = true,
                        connectedClients = 0,
                        fps = config.fps,
                        resolution = config.resolution,
                        startTime = startTime
                    ))
                    
                    call.respond(HttpStatusCode.OK, ApiResponse(true, 
                        mapOf(
                            "message" to "MJPEG stream started",
                            "config" to config,
                            "streamUrl" to "http://localhost:8081/stream"
                        )
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, 
                        ApiResponse<Nothing>(false, message = "Failed to start stream: ${e.message}")
                    )
                }
            }
            
            post("/stop") {
                streamStatus.set(StreamStatus(false, 0, 0, "1080p", null))
                call.respond(HttpStatusCode.OK, ApiResponse(true, 
                    mapOf("message" to "MJPEG stream stopped")
                ))
            }
            
            get("/stream") {
                val status = streamStatus.get()
                if (!status.isStreaming) {
                    call.respond(HttpStatusCode.ServiceUnavailable, 
                        ApiResponse<Nothing>(false, message = "Stream not active")
                    )
                    return@get
                }
                
                val updatedStatus = status.copy(connectedClients = status.connectedClients + 1)
                streamStatus.set(updatedStatus)
                
                call.response.header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                call.response.header("Cache-Control", "no-cache")
                call.response.header("Connection", "close")
                
                call.respondText("--frame\r\nContent-Type: image/jpeg\r\n\r\n[MOCK_JPEG_DATA]\r\n")
            }
        }
    }
}

fun main() {
    val server = MjpegApiServer()
    server.start(8081)
    Runtime.getRuntime().addShutdownHook(Thread { server.stop() })
    Thread.currentThread().join()
}
