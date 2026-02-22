package info.dvkr.screenstream.mjpeg.internal

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioPlaybackCaptureConfiguration
import android.media.AudioRecord
import android.media.projection.MediaProjection
import android.os.Build
import androidx.annotation.RequiresApi
import androidx.core.content.ContextCompat
import com.elvishew.xlog.XLog
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import kotlin.math.max

@RequiresApi(Build.VERSION_CODES.Q)
internal class AudioStreamer(private val context: Context) {

    private val _audioFlow = MutableSharedFlow<ByteArray>(
        replay = 0,
        extraBufferCapacity = 128,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    internal val audioFlow: SharedFlow<ByteArray> = _audioFlow.asSharedFlow()

    private var audioRecord: AudioRecord? = null
    private val isStreaming = AtomicBoolean(false)
    private var audioThread: Thread? = null

    internal fun start(mediaProjection: MediaProjection): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            XLog.e("[AudioStreamer::start] Android 10+ required")
            return false
        }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
             XLog.e("[AudioStreamer::start] RECORD_AUDIO permission missing")
             return false
        }
        if (isStreaming.get()) return true

        try {
            val config = AudioPlaybackCaptureConfiguration.Builder(mediaProjection)
                .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
                .addMatchingUsage(AudioAttributes.USAGE_GAME)
                .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)
                .build()

            val format = AudioFormat.Builder()
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setSampleRate(48000)
                .setChannelMask(AudioFormat.CHANNEL_IN_STEREO)
                .build()

            val minBufferSize = AudioRecord.getMinBufferSize(48000, AudioFormat.CHANNEL_IN_STEREO, AudioFormat.ENCODING_PCM_16BIT)
            val bufferSize = max(minBufferSize * 2, 4096)

            audioRecord = AudioRecord.Builder()
                .setAudioFormat(format)
                .setBufferSizeInBytes(bufferSize)
                .setAudioPlaybackCaptureConfig(config)
                .build()

            audioRecord?.startRecording()
            isStreaming.set(true)
            XLog.d("[AudioStreamer::start] Started")

            audioThread = thread(name = "AudioCaptureThread") {
                val buffer = ByteArray(4096)

                while (isStreaming.get()) {
                     val read = audioRecord?.read(buffer, 0, buffer.size) ?: -1
                     if (read > 0) {
                         _audioFlow.tryEmit(buffer.copyOf(read))
                     } else {
                         if (read < 0) {
                             XLog.e("[AudioStreamer::thread] Read Error: $read")
                         }
                     }
                }

                try {
                    audioRecord?.stop()
                    audioRecord?.release()
                } catch (e: Exception) {
                    XLog.e("[AudioStreamer::thread] Release Error", e)
                }
                audioRecord = null
                XLog.d("[AudioStreamer::thread] Stopped")
            }
            return true

        } catch (e: Exception) {
             XLog.e("[AudioStreamer::start] Error", e)
             try { audioRecord?.stop() } catch (_: Exception) {}
             try { audioRecord?.release() } catch (_: Exception) {}
             audioRecord = null
             return false
        }
    }

    internal fun stop() {
        isStreaming.set(false)
        try {
            audioThread?.join(1000)
        } catch (ignore: InterruptedException) {}
        XLog.d("[AudioStreamer::stop] Done")
    }
}
