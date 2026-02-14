package info.dvkr.screenstream.input

import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.cio.*
import io.ktor.server.engine.*
import io.ktor.server.plugins.cors.routing.*
import io.ktor.server.routing.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * HTTP API Server for remote input control
 *
 * Provides REST endpoints for tap, swipe, key, and text input
 */
public class InputHttpServer(
    private val port: Int = 8084
) {
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
        routing { installInputRoutes() }
    }
}
