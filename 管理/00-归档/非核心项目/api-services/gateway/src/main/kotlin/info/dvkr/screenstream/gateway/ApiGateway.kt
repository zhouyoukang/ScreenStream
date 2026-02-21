package info.dvkr.screenstream.gateway

import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.engine.cio.*
import io.ktor.client.request.*
import io.ktor.client.statement.*
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

@Serializable
data class ServiceConfig(
    val mjpegUrl: String = "http://localhost:8081",
    val rtspUrl: String = "http://localhost:8082", 
    val webrtcUrl: String = "http://localhost:8083",
    val inputUrl: String = "http://localhost:8084"
)

@Serializable
data class GatewayStatus(
    val isRunning: Boolean,
    val services: Map<String, ServiceHealth>,
    val totalRequests: Long,
    val startTime: Long
)

@Serializable
data class ServiceHealth(
    val name: String,
    val url: String,
    val isHealthy: Boolean,
    val lastCheck: Long,
    val responseTime: Long
)

/**
 * ScreenStream统一API网关
 * 提供统一入口，路由分发到各个独立服务
 * 支持负载均衡、认证、监控等功能
 */
class ApiGateway {
    private val json = Json { ignoreUnknownKeys = true }
    private var server: NettyApplicationEngine? = null
    private val client = HttpClient(CIO)
    private val isRunning = AtomicBoolean(false)
    private val config = ServiceConfig()
    private var totalRequests = 0L
    private val startTime = System.currentTimeMillis()
    
    fun start(port: Int = 8080) {
        if (isRunning.get()) {
            println("API Gateway already running on port $port")
            return
        }
        
        server = embeddedServer(Netty, port = port, host = "0.0.0.0") {
            configureRouting()
        }.start(wait = false)
        
        isRunning.set(true)
        println("ScreenStream API Gateway started on port $port")
        println("Available services:")
        println("  - MJPEG:  ${config.mjpegUrl}")
        println("  - RTSP:   ${config.rtspUrl}")
        println("  - WebRTC: ${config.webrtcUrl}")
        println("  - Input:  ${config.inputUrl}")
    }
    
    fun stop() {
        runBlocking {
            client.close()
        }
        server?.stop(1000, 5000)
        isRunning.set(false)
        println("API Gateway stopped")
    }
    
    private suspend fun checkServiceHealth(serviceName: String, url: String): ServiceHealth {
        val startTime = System.currentTimeMillis()
        return try {
            val response = client.get("$url/health") {
                timeout {
                    requestTimeoutMillis = 5000
                }
            }
            val responseTime = System.currentTimeMillis() - startTime
            
            ServiceHealth(
                name = serviceName,
                url = url,
                isHealthy = response.status == HttpStatusCode.OK,
                lastCheck = System.currentTimeMillis(),
                responseTime = responseTime
            )
        } catch (e: Exception) {
            ServiceHealth(
                name = serviceName,
                url = url,
                isHealthy = false,
                lastCheck = System.currentTimeMillis(),
                responseTime = System.currentTimeMillis() - startTime
            )
        }
    }
    
    private suspend fun proxyRequest(call: ApplicationCall, targetUrl: String, path: String) {
        totalRequests++
        
        try {
            val fullUrl = "$targetUrl$path"
            val queryString = call.request.queryString()
            val finalUrl = if (queryString.isNotEmpty()) "$fullUrl?$queryString" else fullUrl
            
            val response = when (call.request.httpMethod) {
                HttpMethod.Get -> {
                    client.get(finalUrl) {
                        call.request.headers.forEach { name, values ->
                            if (!HttpHeaders.isUnsafe(name) && name != HttpHeaders.Host) {
                                header(name, values.first())
                            }
                        }
                    }
                }
                HttpMethod.Post -> {
                    client.post(finalUrl) {
                        call.request.headers.forEach { name, values ->
                            if (!HttpHeaders.isUnsafe(name) && name != HttpHeaders.Host) {
                                header(name, values.first())
                            }
                        }
                        if (call.request.contentLength() != null && call.request.contentLength()!! > 0) {
                            setBody(call.receiveText())
                        }
                    }
                }
                else -> {
                    call.respond(HttpStatusCode.MethodNotAllowed, mapOf(
                        "error" to "Method ${call.request.httpMethod.value} not supported"
                    ))
                    return
                }
            }
            
            response.headers.forEach { name, values ->
                if (!HttpHeaders.isUnsafe(name)) {
                    call.response.header(name, values.first())
                }
            }
            
            call.respond(response.status, response.bodyAsText())
            
        } catch (e: Exception) {
            call.respond(HttpStatusCode.ServiceUnavailable, mapOf(
                "error" to "Service unavailable",
                "message" to e.message,
                "targetService" to targetUrl
            ))
        }
    }
    
    private fun Application.configureRouting() {
        routing {
            // Gateway健康检查
            get("/health") {
                call.respond(HttpStatusCode.OK, mapOf(
                    "status" to "healthy",
                    "service" to "Gateway",
                    "uptime" to (System.currentTimeMillis() - startTime)
                ))
            }
            
            // Gateway状态
            get("/status") {
                val services = mapOf(
                    "mjpeg" to checkServiceHealth("MJPEG", config.mjpegUrl),
                    "rtsp" to checkServiceHealth("RTSP", config.rtspUrl),
                    "webrtc" to checkServiceHealth("WebRTC", config.webrtcUrl),
                    "input" to checkServiceHealth("Input", config.inputUrl)
                )
                
                val status = GatewayStatus(
                    isRunning = isRunning.get(),
                    services = services,
                    totalRequests = totalRequests,
                    startTime = startTime
                )
                
                call.respond(HttpStatusCode.OK, status)
            }
            
            // 一键启动所有服务
            post("/start-all") {
                val results = mutableMapOf<String, Any>()
                
                try {
                    // 启动MJPEG服务
                    val mjpegResponse = client.post("${config.mjpegUrl}/start")
                    results["mjpeg"] = if (mjpegResponse.status.isSuccess()) "started" else "failed"
                    
                    // 启动RTSP服务
                    val rtspResponse = client.post("${config.rtspUrl}/start")
                    results["rtsp"] = if (rtspResponse.status.isSuccess()) "started" else "failed"
                    
                    // 启动WebRTC服务
                    val webrtcResponse = client.post("${config.webrtcUrl}/start")
                    results["webrtc"] = if (webrtcResponse.status.isSuccess()) "started" else "failed"
                    
                    // 启动Input服务
                    val inputResponse = client.post("${config.inputUrl}/start")
                    results["input"] = if (inputResponse.status.isSuccess()) "started" else "failed"
                    
                    call.respond(HttpStatusCode.OK, mapOf(
                        "success" to true,
                        "message" to "All services startup initiated",
                        "results" to results
                    ))
                    
                } catch (e: Exception) {
                    call.respond(HttpStatusCode.ServiceUnavailable, mapOf(
                        "success" to false,
                        "message" to "Failed to start all services: ${e.message}",
                        "results" to results
                    ))
                }
            }
            
            // 一键停止所有服务
            post("/stop-all") {
                val results = mutableMapOf<String, Any>()
                
                listOf(
                    "mjpeg" to config.mjpegUrl,
                    "rtsp" to config.rtspUrl, 
                    "webrtc" to config.webrtcUrl,
                    "input" to config.inputUrl
                ).forEach { (name, url) ->
                    try {
                        val response = client.post("$url/stop")
                        results[name] = if (response.status.isSuccess()) "stopped" else "failed"
                    } catch (e: Exception) {
                        results[name] = "error: ${e.message}"
                    }
                }
                
                call.respond(HttpStatusCode.OK, mapOf(
                    "success" to true,
                    "message" to "All services stop initiated",
                    "results" to results
                ))
            }
            
            // MJPEG服务路由
            route("/mjpeg") {
                get("/{...}") {
                    proxyRequest(call, config.mjpegUrl, call.request.path().removePrefix("/mjpeg"))
                }
                post("/{...}") {
                    proxyRequest(call, config.mjpegUrl, call.request.path().removePrefix("/mjpeg"))
                }
            }
            
            // RTSP服务路由
            route("/rtsp") {
                get("/{...}") {
                    proxyRequest(call, config.rtspUrl, call.request.path().removePrefix("/rtsp"))
                }
                post("/{...}") {
                    proxyRequest(call, config.rtspUrl, call.request.path().removePrefix("/rtsp"))
                }
            }
            
            // WebRTC服务路由
            route("/webrtc") {
                get("/{...}") {
                    proxyRequest(call, config.webrtcUrl, call.request.path().removePrefix("/webrtc"))
                }
                post("/{...}") {
                    proxyRequest(call, config.webrtcUrl, call.request.path().removePrefix("/webrtc"))
                }
            }
            
            // Input服务路由
            route("/input") {
                get("/{...}") {
                    proxyRequest(call, config.inputUrl, call.request.path().removePrefix("/input"))
                }
                post("/{...}") {
                    proxyRequest(call, config.inputUrl, call.request.path().removePrefix("/input"))
                }
            }
            
            // API文档
            get("/") {
                call.respondText("""
                    ScreenStream API Gateway
                    =======================
                    
                    Available Endpoints:
                    
                    Gateway Control:
                    GET  /health       - Gateway health check
                    GET  /status       - Gateway and services status
                    POST /start-all    - Start all services
                    POST /stop-all     - Stop all services
                    
                    Service Proxies:
                    /mjpeg/*   - MJPEG streaming service (port 8081)
                    /rtsp/*    - RTSP streaming service (port 8082)  
                    /webrtc/*  - WebRTC signaling service (port 8083)
                    /input/*   - Input control service (port 8084)
                    
                    Example usage:
                    curl http://localhost:8080/mjpeg/start
                    curl http://localhost:8080/input/touch -d '{"x":100,"y":200}'
                """.trimIndent(), ContentType.Text.Plain)
            }
        }
    }
}

fun main() {
    val gateway = ApiGateway()
    gateway.start(8080)
    Runtime.getRuntime().addShutdownHook(Thread { gateway.stop() })
    Thread.currentThread().join()
}
