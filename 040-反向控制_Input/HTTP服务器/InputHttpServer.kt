package info.dvkr.screenstream.input

import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import android.content.Context
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.cio.*
import io.ktor.server.engine.*
import io.ktor.server.plugins.cors.routing.*
import io.ktor.server.plugins.forwardedheaders.*
import io.ktor.server.request.header
import io.ktor.server.request.httpMethod
import io.ktor.server.request.path
import io.ktor.server.response.respondText
import io.ktor.server.routing.*
import io.ktor.server.websocket.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
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
    private val scope = CoroutineScope(Dispatchers.IO)

    // ==================== Server Lifecycle ====================

    public fun start() {
        if (server != null) {
            XLog.w(getLog("InputHttpServer", "Server already running"))
            return
        }

        scope.launch {
            try {
                server = embeddedServer(CIO, port = port) {
                    install(WebSockets)
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
                        allowMethod(HttpMethod.Options)
                        allowNonSimpleContentTypes = true
                    }
                    install(ForwardedHeaders)
                    val server = this@InputHttpServer
                    intercept(ApplicationCallPipeline.Plugins) {
                        val token = server.getAuthToken()
                        if (token.isEmpty()) return@intercept
                        if (call.request.httpMethod == HttpMethod.Options) return@intercept
                        val path = call.request.path()
                        if (path == "/status" || path == "/health") return@intercept
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
        routing { installInputRoutes() }
    }
}
