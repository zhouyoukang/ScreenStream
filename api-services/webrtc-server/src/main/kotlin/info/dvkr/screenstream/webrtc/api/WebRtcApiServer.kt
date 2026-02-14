package info.dvkr.screenstream.webrtc.api

import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.engine.*
import io.ktor.server.netty.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import io.ktor.server.websocket.*
import io.ktor.websocket.*
import kotlinx.coroutines.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.ConcurrentHashMap
import java.time.Duration

@Serializable
data class WebRtcConfig(
    val iceServers: List<String> = listOf("stun:stun.l.google.com:19302"),
    val videoCodec: String = "VP8",
    val audioCodec: String = "OPUS",
    val maxBitrate: Int = 2500000,
    val enableAudio: Boolean = true
)

@Serializable
data class SdpMessage(
    val type: String, // "offer" or "answer"
    val sdp: String
)

@Serializable
data class IceCandidate(
    val candidate: String,
    val sdpMid: String?,
    val sdpMLineIndex: Int?
)

@Serializable
data class WebRtcStatus(
    val isSignalingActive: Boolean,
    val connectedPeers: Int,
    val config: WebRtcConfig,
    val startTime: Long?
)

@Serializable
data class PeerConnection(
    val peerId: String,
    val remoteAddress: String,
    val connectionState: String,
    val connectTime: Long
)

/**
 * WebRTC信令服务API独立版本
 * 提供WebRTC Signaling Server和RESTful API接口
 */
class WebRtcApiServer {
    private val json = Json { ignoreUnknownKeys = true }
    private var server: NettyApplicationEngine? = null
    private val isRunning = AtomicBoolean(false)
    private val currentConfig = AtomicReference(WebRtcConfig())
    private val peers = ConcurrentHashMap<String, PeerConnection>()
    private val websocketSessions = ConcurrentHashMap<String, DefaultWebSocketSession>()
    
    fun start(port: Int = 8083) {
        if (isRunning.get()) {
            println("WebRTC API Server already running on port $port")
            return
        }
        
        server = embeddedServer(Netty, port = port, host = "0.0.0.0") {
            install(WebSockets) {
                pingPeriod = Duration.ofSeconds(15)
                timeout = Duration.ofSeconds(15)
                maxFrameSize = Long.MAX_VALUE
                masking = false
            }
            configureRouting()
        }.start(wait = false)
        
        isRunning.set(true)
        println("WebRTC API Server started on port $port")
    }
    
    fun stop() {
        server?.stop(1000, 5000)
        peers.clear()
        websocketSessions.clear()
        isRunning.set(false)
        println("WebRTC API Server stopped")
    }
    
    private fun getCurrentStatus(): WebRtcStatus {
        return WebRtcStatus(
            isSignalingActive = isRunning.get(),
            connectedPeers = peers.size,
            config = currentConfig.get(),
            startTime = if (isRunning.get()) System.currentTimeMillis() else null
        )
    }
    
    private fun Application.configureRouting() {
        routing {
            get("/health") {
                call.respond(HttpStatusCode.OK, mapOf("status" to "healthy", "service" to "WebRTC"))
            }
            
            get("/status") {
                call.respond(HttpStatusCode.OK, getCurrentStatus())
            }
            
            post("/start") {
                try {
                    val config = if (call.request.contentLength() != null && call.request.contentLength()!! > 0) {
                        json.decodeFromString<WebRtcConfig>(call.receiveText())
                    } else {
                        WebRtcConfig()
                    }
                    
                    currentConfig.set(config)
                    
                    call.respond(HttpStatusCode.OK, mapOf(
                        "success" to true,
                        "message" to "WebRTC signaling server started",
                        "config" to config,
                        "signalingUrl" to "ws://localhost:8083/signaling"
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Failed to start WebRTC server: ${e.message}"
                    ))
                }
            }
            
            post("/stop") {
                peers.clear()
                websocketSessions.values.forEach { session ->
                    try {
                        session.close()
                    } catch (e: Exception) {
                        // Ignore close errors
                    }
                }
                websocketSessions.clear()
                
                call.respond(HttpStatusCode.OK, mapOf(
                    "success" to true,
                    "message" to "WebRTC signaling server stopped"
                ))
            }
            
            get("/peers") {
                call.respond(HttpStatusCode.OK, mapOf(
                    "success" to true,
                    "peers" to peers.values.toList()
                ))
            }
            
            post("/offer") {
                try {
                    val sdpMessage = json.decodeFromString<SdpMessage>(call.receiveText())
                    
                    // 创建模拟应答SDP
                    val answerSdp = SdpMessage(
                        type = "answer",
                        sdp = "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n[MOCK_ANSWER_SDP]"
                    )
                    
                    call.respond(HttpStatusCode.OK, mapOf(
                        "success" to true,
                        "answer" to answerSdp
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Invalid SDP offer: ${e.message}"
                    ))
                }
            }
            
            post("/candidate") {
                try {
                    val candidate = json.decodeFromString<IceCandidate>(call.receiveText())
                    
                    // 模拟ICE候选处理
                    call.respond(HttpStatusCode.OK, mapOf(
                        "success" to true,
                        "message" to "ICE candidate processed",
                        "candidate" to candidate
                    ))
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.BadRequest, mapOf(
                        "success" to false,
                        "message" to "Invalid ICE candidate: ${e.message}"
                    ))
                }
            }
            
            get("/config") {
                call.respond(HttpStatusCode.OK, currentConfig.get())
            }
            
            post("/config") {
                try {
                    val config = json.decodeFromString<WebRtcConfig>(call.receiveText())
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
            
            // WebSocket信令端点
            webSocket("/signaling") {
                val peerId = "peer_${System.currentTimeMillis()}"
                val peerConnection = PeerConnection(
                    peerId = peerId,
                    remoteAddress = call.request.origin.remoteHost,
                    connectionState = "connected",
                    connectTime = System.currentTimeMillis()
                )
                
                peers[peerId] = peerConnection
                websocketSessions[peerId] = this
                
                try {
                    send(Frame.Text(json.encodeToString(mapOf(
                        "type" to "connected",
                        "peerId" to peerId
                    ))))
                    
                    for (frame in incoming) {
                        when (frame) {
                            is Frame.Text -> {
                                val message = frame.readText()
                                // 广播给其他peer（简单实现）
                                websocketSessions.values.forEach { session ->
                                    if (session != this) {
                                        try {
                                            session.send(Frame.Text(message))
                                        } catch (e: Exception) {
                                            // Ignore send errors
                                        }
                                    }
                                }
                            }
                            else -> { }
                        }
                    }
                } catch (e: Exception) {
                    // Connection closed
                } finally {
                    peers.remove(peerId)
                    websocketSessions.remove(peerId)
                }
            }
        }
    }
}

fun main() {
    val server = WebRtcApiServer()
    server.start(8083)
    Runtime.getRuntime().addShutdownHook(Thread { server.stop() })
    Thread.currentThread().join()
}
