package com.github.audiocenter

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioPlaybackCaptureConfiguration
import android.media.AudioRecord
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat // Import Component
import io.ktor.server.application.*
import io.ktor.server.cio.*
import io.ktor.server.engine.*
import io.ktor.server.http.content.*
import io.ktor.server.routing.*
import io.ktor.server.websocket.*
import io.ktor.websocket.*
import kotlinx.coroutines.*
import java.util.concurrent.atomic.AtomicBoolean

class AudioStreamingService : Service() {

    private val NOTIFICATION_ID = 101
    private val CHANNEL_ID = "AudioCenterChannel"
    private var server: EmbeddedServer<*, *>? = null
    private val isStreaming = AtomicBoolean(false)
    private var audioRecord: AudioRecord? = null
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    
    private val clients = java.util.Collections.synchronizedList(ArrayList<DefaultWebSocketSession>())
    
    // MediaProjection logic
    private var mediaProjectionManager: MediaProjectionManager? = null
    private var mediaProjection: MediaProjection? = null

    companion object {
        const val EXTRA_SOURCE_TYPE = "SOURCE_TYPE"
        const val EXTRA_RESULT_CODE = "RESULT_CODE"
        const val EXTRA_RESULT_DATA = "RESULT_DATA"
        const val SOURCE_MIC = 0
        const val SOURCE_SYSTEM = 1
    }

    override fun onBind(intent: Intent): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        mediaProjectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        createNotificationChannel()
        // Default start as mic temporarily, will be updated by startForeground in onStartCommand
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val type = intent?.getIntExtra(EXTRA_SOURCE_TYPE, SOURCE_MIC) ?: SOURCE_MIC
        
        // Setup Notification based on Type
        val notif = createNotification(type)
        
        // Important: Specify foregroundServiceType
        val typeFlag = if (type == SOURCE_SYSTEM && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
        } else {
             ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
        }
        
        ServiceCompat.startForeground(this, NOTIFICATION_ID, notif, typeFlag)

        if (!isStreaming.get()) {
            startServer()
            if (type == SOURCE_SYSTEM && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val code = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
                val data = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
                if (code != 0 && data != null) {
                    startAudioCapture(type, code, data)
                } else {
                    Log.e("AudioCenter", "Missing MediaProjection Data")
                    stopSelf()
                }
            } else {
                startAudioCapture(SOURCE_MIC, 0, null)
            }
        }
        
        return START_NOT_STICKY
    }

    private fun startServer() {
        serviceScope.launch {
            if (server == null) {
                server = embeddedServer(CIO, port = 8085) {
                    install(WebSockets)
                    routing {
                        webSocket("/stream/audio") {
                            clients.add(this)
                            Log.d("AudioCenter", "Client connected")
                            try {
                                incoming.consumeEach { } 
                            } finally {
                                clients.remove(this)
                                Log.d("AudioCenter", "Client disconnected")
                            }
                        }
                        staticResources("/dashboard", "dashboard", index = "index.html")
                    }
                }
                server?.start(wait = true)
            }
        }
    }

    private fun startAudioCapture(sourceType: Int, resultCode: Int, resultData: Intent?) {
        isStreaming.set(true)
        serviceScope.launch(Dispatchers.IO) {
            Log.d("AudioCenter", "Starting Audio Capture. Type: $sourceType")
            
            // 16kHz Mono 16-bit PCM
            val sampleRate = 16000
            val channelConfig = AudioFormat.CHANNEL_IN_MONO
            val audioFormat = AudioFormat.ENCODING_PCM_16BIT
            val minBufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)
            val bufferSize = if (minBufferSize > 0) minBufferSize * 2 else 4096
            
            try {
                if (sourceType == SOURCE_SYSTEM && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    mediaProjection = mediaProjectionManager?.getMediaProjection(resultCode, resultData!!)
                    val playbackConfig = AudioPlaybackCaptureConfiguration.Builder(mediaProjection!!)
                        .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
                        .addMatchingUsage(AudioAttributes.USAGE_GAME)
                        .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)
                        .build()
                        
                    audioRecord = AudioRecord.Builder()
                        .setAudioFormat(
                            AudioFormat.Builder()
                                .setEncoding(audioFormat)
                                .setSampleRate(sampleRate)
                                .setChannelMask(channelConfig)
                                .build()
                        )
                        .setBufferSizeInBytes(bufferSize)
                        .setAudioPlaybackCaptureConfig(playbackConfig)
                        .build()
                } else {
                    // Classic Mic
                    audioRecord = AudioRecord(
                        android.media.MediaRecorder.AudioSource.MIC,
                        sampleRate,
                        channelConfig,
                        audioFormat,
                        bufferSize
                    )
                }

                if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                    Log.e("AudioCenter", "AudioRecord init failed! State: ${audioRecord?.state}")
                    return@launch
                }

                audioRecord?.startRecording()
                Log.d("AudioCenter", "Recording started")

                val buffer = ByteArray(2048) 
                
                while (isStreaming.get() && isActive) {
                    val read = audioRecord?.read(buffer, 0, buffer.size) ?: -1
                    if (read > 0) {
                        val data = buffer.copyOf(read)
                        synchronized(clients) {
                            clients.forEach { client ->
                                launch {
                                     try { client.send(Frame.Binary(true, data)) } catch (e: Exception) {}
                                }
                            }
                        }
                    } else {
                         delay(5)
                    }
                }
            } catch (e: Exception) {
                Log.e("AudioCenter", "Capture Loop Error", e)
            } finally {
                try {
                    audioRecord?.stop()
                    audioRecord?.release()
                    mediaProjection?.stop()
                } catch (e: Exception) { }
                Log.d("AudioCenter", "Audio Capture Stopped")
            }
        }
    }

    override fun onDestroy() {
        isStreaming.set(false)
        server?.stop(1000, 2000)
        serviceScope.cancel()
        super.onDestroy()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(CHANNEL_ID, "Audio Stream Service", NotificationManager.IMPORTANCE_LOW)
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(type: Int): Notification {
        val text = if (type == SOURCE_SYSTEM) "Streaming System Audio..." else "Streaming Microphone..."
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("AudioCenter Source")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .build()
    }
}
