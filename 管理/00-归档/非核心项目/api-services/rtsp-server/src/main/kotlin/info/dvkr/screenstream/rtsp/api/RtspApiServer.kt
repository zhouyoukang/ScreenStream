package info.dvkr.screenstream.rtsp.api

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
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.ConcurrentHashMap

@Serializable
data class RtspConfig(
    val codec: String = "H264",
    val bitrate: Int = 2000000,
    val fps: Int = 30,
    val resolution: String = "1080p",
    val port: Int = 8554
)

@Serializable
data class RtspStatus(
    val isStreaming: Boolean,
    val connectedClients: List<String>,
    val codec: String,
    val bitrate: Int,
    val fps: Int,
    val resolution: String,
    val rtspUrl: String,
    val startTime: Long?
)

@Serializable
data class ClientInfo(
    val clientId: String,
    val remoteAddress: String,
    val connectTime: Long,
    val isActive: Boolean
)

/**
 * RTSP服务API独立版本
 * 提供RESTful API接口管理RTSP流媒体服务
 */
class RtspApiServer {
    private val json = Json { ignoreUnknownKeys = true }
    private var server: NettyApplicationEngine? = null
    private val isRunning = AtomicBoolean(false)
    private val currentConfig = AtomicReference(RtspConfig())
    private val clients = ConcurrentHashMap<String, ClientInfo>()
    
    fun start(port: Int = 8082) {
        if (isRunning.get()) {
            println("RTSP API Server already running on port $port")
            return
        }
        
        server = embeddedServer(Netty, port = port, host = "0.0.0.0") {
            configureRouting()
        }.start(wait = false)
        
        isRunning.set(true)
        println("RTSP API Server started on port $port")
    }
    
    fun stop() {
        server?.stop(1000, 5000)
        clients.clear()
        isRunning.set(false)
        println("RTSP API Server stopped")
    }
    
    private fun getCurrentStatus(): RtspStatus {
        val config = currentConfig.get()
        val activeClients = clients.values.filter { it.isActive }.map { it.clientId }
        
        return RtspStatus(
            isStreaming = isRunning.get(),
            connectedClients = activeClients,
            codec = config.codec,
            bitrate = config.bitrate,
            fps = config.fps,
            resolution = config.resolution,
            rtspUrl = "rtsp://localhost:${config.port}/live",
            startTime = if (isRunning.get()) System.currentTimeMillis() else null
        )
    }
    
    private fun Application.configureRouting() {
        routing {
            get("/health") {
                call.respond(HttpStatusCode.OK, mapOf("status" to "healthy", "service" to "RTSP"))
            }
            
            get("/status") {
                call.respond(HttpStatusCode.OK, getCurrentStatus())
            }
            
            post("/start") {
                try {
                    val config = if (call.request.contentLength() != null && call.request.contentLength()!! > 0) {
                        json.decodeFromString<RtspConfig>(call.receiveText())
                    } else {
                        RtspConfig()
                    }
                    
                    currentConfig.set(config)
                    
                    call.respond(HttpStatusCode.OK, mapOf(
                        "success" to true,
                        "message" to "RTSP server started",
                        "config" to config,
                        "rtspUrl" to "rtsp://localhost:${config.port}/live"
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Failed to start RTSP server: ${e.message}"
                    ))
                }
            }
            
            post("/stop") {
                clients.clear()
                call.respond(HttpStatusCode.OK, mapOf(
                    "success" to true,
                    "message" to "RTSP server stopped"
                ))
            }
            
            get("/clients") {
                call.respond(HttpStatusCode.OK, mapOf(
                    "success" to true,
                    "clients" to clients.values.toList()
                ))
            }
            
            post("/clients/{clientId}/disconnect") {
                val clientId = call.parameters["clientId"]
                if (clientId != null && clients.containsKey(clientId)) {
                    clients.remove(clientId)
                    call.respond(HttpStatusCode.OK, mapOf(
                        "success" to true,
                        "message" to "Client $clientId disconnected"
                    ))
                } else {
                    call.respond(HttpStatusCode.NotFound, mapOf(
                        "success" to false,
                        "message" to "Client not found"
                    ))
                }
            }
            
            get("/config") {
                call.respond(HttpStatusCode.OK, currentConfig.get())
            }
            
            post("/config") {
                try {
                    val config = json.decodeFromString<RtspConfig>(call.receiveText())
                    currentConfig.set(config)
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
            
            // 模拟RTSP客户端连接
            post("/simulate/connect") {
                val clientId = "client_${System.currentTimeMillis()}"
                val clientInfo = ClientInfo(
                    clientId = clientId,
                    remoteAddress = "127.0.0.1",
                    connectTime = System.currentTimeMillis(),
                    isActive = true
                )
                clients[clientId] = clientInfo
                
                call.respond(HttpStatusCode.OK, mapOf(
                    "success" to true,
                    "message" to "Client connected",
                    "clientInfo" to clientInfo
                ))
            }
        }
    }
}

fun main() {
    val server = RtspApiServer()
    server.start(8082)
    Runtime.getRuntime().addShutdownHook(Thread { server.stop() })
    Thread.currentThread().join()
}
