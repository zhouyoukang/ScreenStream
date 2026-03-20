package info.dvkr.screenstream.mjpeg.internal

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.Build
import android.os.Bundle
import android.view.Surface
import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.nio.ByteBuffer

internal data class H264Frame(
    val data: ByteArray,
    val type: Int, // 0 = Config (SPS/PPS), 1 = Key Frame, 2 = Delta Frame
    val timestamp: Long
) {
    internal companion object {
        const val TYPE_CONFIG: Int = 0
        const val TYPE_KEY_FRAME: Int = 1
        const val TYPE_DELTA_FRAME: Int = 2

        // Helper to check NAL type from byte
        fun isKeyFrame(byte: Byte): Boolean {
            return (byte.toInt() and 0x1F) == 5
        }
    }
}

internal class H264Encoder(
    private val width: Int,
    private val height: Int,
    private val densityDpi: Int,
    private val mimeType: String = MediaFormat.MIMETYPE_VIDEO_AVC,
    private val bitRate: Int = 12000000, // 12Mbps default (LAN 1080p); caller should pass resolution-adaptive value
    private val frameRate: Int = 30,
    private val callback: (H264Frame) -> Unit
) {

    private var mediaCodec: MediaCodec? = null
    private var inputSurface: Surface? = null
    private var isRunning = false

    init {
        XLog.d(getLog("init", "w:$width h:$height dpi:$densityDpi bitrate:$bitRate fps:$frameRate"))
        initializeCodec()
    }

    private fun initializeCodec() {
        try {
            val format = MediaFormat.createVideoFormat(mimeType, width, height)
            format.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface)
            format.setInteger(MediaFormat.KEY_BIT_RATE, bitRate)
            format.setInteger(MediaFormat.KEY_FRAME_RATE, frameRate)
            format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1) // 1 second between keyframes

            // Force High Profile for best quality per bitrate (Baseline = worst)
            if (mimeType == MediaFormat.MIMETYPE_VIDEO_AVC) {
                try {
                    format.setInteger(MediaFormat.KEY_PROFILE, MediaCodecInfo.CodecProfileLevel.AVCProfileHigh)
                    format.setInteger(MediaFormat.KEY_LEVEL, MediaCodecInfo.CodecProfileLevel.AVCLevel4)
                } catch (e: Exception) {
                    XLog.w(getLog("initializeCodec", "High Profile not supported, using device default"))
                }
            }

            // Low-latency encoding optimizations
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                format.setInteger(MediaFormat.KEY_ALLOW_FRAME_DROP, 0) // Don't drop frames
            }
            format.setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR)
            format.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 0) // No limit

            // Try to set low latency mode if supported
            try {
                format.setInteger(MediaFormat.KEY_LATENCY, 0)
            } catch (e: Exception) {
                // KEY_LATENCY not supported on this device
            }

            // Explicitly disable B-frames (High Profile can enable them, adding 1-2 frame latency)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                try {
                    format.setInteger(MediaFormat.KEY_MAX_B_FRAMES, 0)
                } catch (e: Exception) {
                    XLog.d(getLog("initializeCodec", "KEY_MAX_B_FRAMES not supported"))
                }
            }

            // Realtime encoding priority (0=realtime, 1=non-realtime)
            try {
                format.setInteger(MediaFormat.KEY_PRIORITY, 0)
            } catch (e: Exception) { }

            // Repeat previous frame for static content (avoids encoder idle → burst on motion)
            try {
                format.setInteger(MediaFormat.KEY_REPEAT_PREVIOUS_FRAME_AFTER, 100000) // 100ms in µs
            } catch (e: Exception) { }

            // Lowest complexity for fastest encoding (0=fastest, less quality per bit)
            try {
                format.setInteger(MediaFormat.KEY_COMPLEXITY, 0)
            } catch (e: Exception) { }

            mediaCodec = MediaCodec.createEncoderByType(mimeType)
            mediaCodec?.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            inputSurface = mediaCodec?.createInputSurface()

            mediaCodec?.setCallback(object : MediaCodec.Callback() {
                override fun onInputBufferAvailable(codec: MediaCodec, index: Int) {
                    // Not used for Surface input
                }

                override fun onOutputBufferAvailable(codec: MediaCodec, index: Int, info: MediaCodec.BufferInfo) {
                    if (!isRunning) {
                        try { codec.releaseOutputBuffer(index, false) } catch (_: Exception) {}
                        return
                    }
                    try {
                        val encodedData = codec.getOutputBuffer(index)
                        if (encodedData != null) {
                            encodedData.position(info.offset)
                            encodedData.limit(info.offset + info.size)

                            val data = ByteArray(info.size)
                            encodedData.get(data)

                            var type = H264Frame.TYPE_DELTA_FRAME
                            if ((info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) {
                                type = H264Frame.TYPE_CONFIG
                            } else if ((info.flags and MediaCodec.BUFFER_FLAG_KEY_FRAME) != 0) {
                                type = H264Frame.TYPE_KEY_FRAME
                            }

                            callback(H264Frame(data, type, info.presentationTimeUs))
                            if (type != H264Frame.TYPE_DELTA_FRAME) {
                                XLog.d(getLog("onOutputBufferAvailable", "type=$type size=${info.size}"))
                            }
                        }
                    } catch (e: Exception) {
                        XLog.e(getLog("onOutputBufferAvailable", e.toString()))
                    } finally {
                        try { codec.releaseOutputBuffer(index, false) } catch (_: Exception) {}
                    }
                }

                override fun onError(codec: MediaCodec, e: MediaCodec.CodecException) {
                    XLog.e(getLog("onError", e.toString()))
                }

                override fun onOutputFormatChanged(codec: MediaCodec, format: MediaFormat) {
                    XLog.d(getLog("onOutputFormatChanged", format.toString()))
                }
            })

            mediaCodec?.start()
            isRunning = true
            XLog.d(getLog("initializeCodec", "Codec started"))

        } catch (e: Exception) {
            XLog.e(getLog("initializeCodec", "Error initializing code: $e"))
            release()
        }
    }

    fun getInputSurface(): Surface? {
        return inputSurface
    }

    fun stop() {
        XLog.d(getLog("stop"))
        isRunning = false
        release()
    }

    fun forceKeyFrame() {
        if (!isRunning) return
        try {
            val bundle = Bundle()
            bundle.putInt(MediaCodec.PARAMETER_KEY_REQUEST_SYNC_FRAME, 0)
            mediaCodec?.setParameters(bundle)
            XLog.d(getLog("forceKeyFrame", "Request sent"))
        } catch (e: Exception) {
            XLog.e(getLog("forceKeyFrame", "Error: $e"))
        }
    }

    fun setBitrate(bitRate: Int) {
        if (!isRunning || mediaCodec == null) return
        try {
            val bundle = Bundle()
            bundle.putInt(MediaCodec.PARAMETER_KEY_VIDEO_BITRATE, bitRate)
            mediaCodec?.setParameters(bundle)
            XLog.i(getLog("setBitrate", "New bitrate: $bitRate"))
        } catch (e: Exception) {
            XLog.e(getLog("setBitrate", "Error: $e"))
        }
    }

    private fun release() {
        try {
            mediaCodec?.stop()
        } catch (e: Exception) { }
        try {
            mediaCodec?.release()
        } catch (e: Exception) { }

        mediaCodec = null
        inputSurface = null
    }
}
