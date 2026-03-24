package info.dvkr.screenstream.input

import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import android.content.Context
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.cio.*
import io.ktor.server.engine.*
import io.ktor.server.plugins.compression.*
import io.ktor.server.plugins.cors.routing.*
import io.ktor.server.plugins.forwardedheaders.*
import io.ktor.server.request.header
import io.ktor.server.request.httpMethod
import io.ktor.server.request.path
import io.ktor.server.response.respondText
import io.ktor.server.routing.*
import io.ktor.server.websocket.*
import java.io.File

/**
 * HTTP API Server for remote input control
 *
 * Provides REST endpoints for tap, swipe, key, and text input
 */
public class InputHttpServer(
    private val context: Context,
    private val port: Int = 8084
) {
    private val authTokenFile = File(context.filesDir, "remote_auth_token")
    @Volatile private var cachedToken = ""
    @Volatile private var tokenFileLastMod = 0L

    init {
        reloadToken()
    }

    public fun reloadToken() {
        try {
            if (authTokenFile.exists()) {
                tokenFileLastMod = authTokenFile.lastModified()
                cachedToken = authTokenFile.readText().trim()
            } else {
                cachedToken = ""
                tokenFileLastMod = 0L
            }
        } catch (_: Exception) {}
    }

    private fun getAuthToken(): String {
        try {
            val mod = if (authTokenFile.exists()) authTokenFile.lastModified() else 0L
            if (mod != tokenFileLastMod) reloadToken()
        } catch (_: Exception) {}
        return cachedToken
    }

    private var server: EmbeddedServer<CIOApplicationEngine, CIOApplicationEngine.Configuration>? = null

    // ==================== Server Lifecycle ====================

    public fun start() {
        if (server != null) {
            XLog.w(getLog("InputHttpServer", "Server already running"))
            return
        }
        try {
            server = embeddedServer(
                factory = CIO,
                rootConfig = serverConfig {
                    module { appModule() }
                },
                configure = {
                    connectionIdleTimeoutSeconds = 45
                    connector {
                        host = "0.0.0.0"
                        port = this@InputHttpServer.port
                    }
                }
            )
            server!!.start(wait = false)
            XLog.i(getLog("InputHttpServer", "Started on port $port"))
        } catch (e: Exception) {
            XLog.e(getLog("InputHttpServer", "Failed to start: ${e.message}"))
        }
    }

    public fun stop() {
        server?.stop(1000, 2000)
        server = null
        XLog.i(getLog("InputHttpServer", "Stopped"))
    }

    public fun isRunning(): Boolean = server != null

    // ==================== Application Module ====================

    private fun Application.appModule() {
        install(Compression) {
            gzip {
                priority = 1.0
                minimumSize(256)
            }
        }
        install(WebSockets) {
            pingPeriodMillis = 45000
            timeoutMillis = 45000
        }
        install(CORS) {
            anyHost()
            allowHeader(HttpHeaders.ContentType)
            allowHeader(HttpHeaders.Accept)
            allowHeader(HttpHeaders.Authorization)
            allowHeader(HttpHeaders.Origin)
            allowHeader(HttpHeaders.AccessControlRequestMethod)
            allowHeader(HttpHeaders.AccessControlRequestHeaders)
            allowMethod(HttpMethod.Post)
            allowMethod(HttpMethod.Get)
            allowMethod(HttpMethod.Put)
            allowMethod(HttpMethod.Delete)
            allowMethod(HttpMethod.Options)
            allowNonSimpleContentTypes = true
        }
        install(ForwardedHeaders)
        val srv = this@InputHttpServer
        intercept(ApplicationCallPipeline.Plugins) {
            val token = srv.getAuthToken()
            if (token.isEmpty()) return@intercept
            if (call.request.httpMethod == HttpMethod.Options) return@intercept
            val path = call.request.path()
            if (path == "/status" || path == "/health" || path == "/capabilities") return@intercept
            val bearer = call.request.header("Authorization")?.removePrefix("Bearer ")?.trim()
            val queryToken = call.request.queryParameters["token"]
            if ((bearer ?: queryToken) != token) {
                call.respondText(
                    """{"error":"unauthorized"}""",
                    ContentType.Application.Json, HttpStatusCode.Unauthorized
                )
                finish()
            }
        }
        routing { installInputRoutes() }
    }
}
