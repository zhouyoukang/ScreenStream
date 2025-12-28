package info.dvkr.screenstream.mjpeg.internal

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.PorterDuff
import android.graphics.SurfaceTexture
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.opengl.GLES20
import android.os.Handler
import android.os.HandlerThread
import android.os.Process
import android.view.Surface
import androidx.core.graphics.createBitmap
import androidx.window.layout.WindowMetricsCalculator
import com.android.grafika.gles.EglCore
import com.android.grafika.gles.FullFrameRect
import com.android.grafika.gles.OffscreenSurface
import com.android.grafika.gles.Texture2dProgram
import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import info.dvkr.screenstream.mjpeg.settings.MjpegSettings
import info.dvkr.screenstream.mjpeg.ui.MjpegError
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min


// https://developer.android.com/media/grow/media-projection
internal class BitmapCapture(
    private val serviceContext: Context,
    private val mjpegSettings: MjpegSettings,
    private val mediaProjection: MediaProjection,
    private val bitmapStateFlow: MutableStateFlow<Bitmap>,
    private val onError: (MjpegError) -> Unit
) {
    private enum class State { INIT, STARTED, DESTROYED, ERROR }

    private class ImageOptions(
        val vrMode: Int = MjpegSettings.Default.VR_MODE_DISABLE,
        val vrIpd: Int = MjpegSettings.Default.VR_IPD, // Inter-Pupillary Distance in mm
        val grayscale: Boolean = MjpegSettings.Default.IMAGE_GRAYSCALE,
        val resizeFactor: Int = MjpegSettings.Values.RESIZE_DISABLED,
        val targetWidth: Int = MjpegSettings.Default.RESOLUTION_WIDTH,
        val targetHeight: Int = MjpegSettings.Default.RESOLUTION_HEIGHT,
        val stretch: Boolean = MjpegSettings.Default.RESOLUTION_STRETCH,
        val rotationDegrees: Int = MjpegSettings.Values.ROTATION_0,
        val maxFPS: Int = MjpegSettings.Default.MAX_FPS,
        val cropLeft: Int = MjpegSettings.Default.IMAGE_CROP_LEFT,
        val cropTop: Int = MjpegSettings.Default.IMAGE_CROP_TOP,
        val cropRight: Int = MjpegSettings.Default.IMAGE_CROP_RIGHT,
        val cropBottom: Int = MjpegSettings.Default.IMAGE_CROP_BOTTOM
    )

    private var state = State.INIT

    private var currentWidth = 0
    private var currentHeight = 0

    private val imageThread: HandlerThread by lazy { HandlerThread("BitmapCapture", Process.THREAD_PRIORITY_BACKGROUND) }
    private val imageThreadHandler: Handler by lazy { Handler(imageThread.looper) }

    @Volatile
    private var imageListener: ImageListener? = null
    private var imageReader: ImageReader? = null
    private var virtualDisplay: VirtualDisplay? = null

    // OpenGL ES fallback fields (from v3.6.4 for VR compatibility)
    @Volatile
    private var fallback: Boolean = false
    @Volatile
    private var fallbackFrameListener: FallbackFrameListener? = null
    private var mEglCore: EglCore? = null
    private var mProducerSide: Surface? = null
    private var mTexture: SurfaceTexture? = null
    private var mTextureId = 0
    private var mConsumerSide: OffscreenSurface? = null
    private var mScreen: FullFrameRect? = null
    private var mBuf: ByteBuffer? = null

    private var reusableBitmap: Bitmap? = null
    private var outputBitmap: Bitmap? = null

    private var imageOptions: ImageOptions = ImageOptions()
    private val coroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private var lastImageMillis = 0L

    private var transformMatrix = Matrix()
    private var transformMatrixDirty = true
    private var paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.DITHER_FLAG or Paint.FILTER_BITMAP_FLAG)


    init {
        XLog.d(getLog("init"))

        mjpegSettings.data.listenForChange(coroutineScope) { data ->
            imageOptions = ImageOptions(
                vrMode = data.vrMode,
                vrIpd = data.vrIpd,
                grayscale = data.imageGrayscale,
                resizeFactor = data.resizeFactor,
                targetWidth = data.resolutionWidth,
                targetHeight = data.resolutionHeight,
                stretch = data.resolutionStretch,
                rotationDegrees = data.rotation,
                maxFPS = data.maxFPS,
                cropLeft = if (data.imageCrop == MjpegSettings.Default.IMAGE_CROP) 0 else data.imageCropLeft,
                cropTop = if (data.imageCrop == MjpegSettings.Default.IMAGE_CROP) 0 else data.imageCropTop,
                cropRight = if (data.imageCrop == MjpegSettings.Default.IMAGE_CROP) 0 else data.imageCropRight,
                cropBottom = if (data.imageCrop == MjpegSettings.Default.IMAGE_CROP) 0 else data.imageCropBottom
            )

            transformMatrixDirty = true
        }

        imageThread.start()
    }

    private fun requireState(vararg requireStates: State) {
        check(state in requireStates) { "BitmapCapture in state [$state] expected ${requireStates.contentToString()}" }
    }

    @Synchronized
    internal fun start(): Boolean {
        XLog.d(getLog("start", "fallback=$fallback"))
        requireState(State.INIT)

        // Use WindowManager.defaultDisplay like v3.6.4 for better VR compatibility
        @Suppress("DEPRECATION")
        val windowManager = serviceContext.getSystemService(Context.WINDOW_SERVICE) as android.view.WindowManager
        @Suppress("DEPRECATION")
        val display = windowManager.defaultDisplay
        
        // Get screen size using Display.getRealSize like v3.6.4
        val screenSize = android.graphics.Point()
        @Suppress("DEPRECATION")
        display.getRealSize(screenSize)
        
        // Cap resolution to prevent integer overflow in ByteBuffer allocation
        // Quest 3 has extremely high resolution that causes overflow
        val maxWidth = 1920
        val maxHeight = 1080
        val scale = min(
            maxWidth.toFloat() / screenSize.x,
            maxHeight.toFloat() / screenSize.y
        ).coerceAtMost(1f)
        
        currentWidth = (screenSize.x * scale).toInt()
        currentHeight = (screenSize.y * scale).toInt()
        XLog.d(getLog("start", "Resolution: ${screenSize.x}x${screenSize.y} -> ${currentWidth}x${currentHeight}"))
        
        // Get densityDpi from Display like v3.6.4
        val displayMetrics = android.util.DisplayMetrics()
        @Suppress("DEPRECATION")
        display.getMetrics(displayMetrics)
        val densityDpi = displayMetrics.densityDpi

        val captureSurface: Surface

        if (fallback.not()) {
            // Standard ImageReader path
            val newImageListener = ImageListener()
            imageListener = newImageListener
            imageReader = ImageReader.newInstance(currentWidth, currentHeight, PixelFormat.RGBA_8888, 2).apply {
                setOnImageAvailableListener(newImageListener, imageThreadHandler)
            }
            captureSurface = imageReader!!.surface
        } else {
            // OpenGL ES fallback path (for VR devices like Quest 3)
            XLog.d(getLog("start", "Using OpenGL ES fallback for VR compatibility"))
            try {
                mEglCore = EglCore(null, EglCore.FLAG_TRY_GLES3 or EglCore.FLAG_RECORDABLE)
                mConsumerSide = OffscreenSurface(mEglCore, currentWidth, currentHeight)
                mConsumerSide!!.makeCurrent()

                val newFallbackListener = FallbackFrameListener(currentWidth, currentHeight)
                fallbackFrameListener = newFallbackListener
                mBuf = ByteBuffer.allocate(currentWidth * currentHeight * 4).apply { order(ByteOrder.nativeOrder()) }
                mScreen = FullFrameRect(Texture2dProgram(Texture2dProgram.ProgramType.TEXTURE_EXT))
                mTextureId = mScreen!!.createTextureObject()
                mTexture = SurfaceTexture(mTextureId, false).apply {
                    setDefaultBufferSize(currentWidth, currentHeight)
                    setOnFrameAvailableListener(newFallbackListener, imageThreadHandler)
                }
                mProducerSide = Surface(mTexture)
                captureSurface = mProducerSide!!

                mEglCore!!.makeNothingCurrent()
            } catch (cause: Throwable) {
                XLog.w(getLog("start", "OpenGL ES fallback failed: ${cause.message}"), cause)
                state = State.ERROR
                onError(MjpegError.UnknownError(cause))
                safeRelease()
                return false
            }
        }

        try {
            virtualDisplay = mediaProjection.createVirtualDisplay(
                "BitmapCaptureVirtualDisplay",
                currentWidth,
                currentHeight,
                densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_PRESENTATION,
                captureSurface,
                null,
                imageThreadHandler
            )
            if (virtualDisplay == null) {
                XLog.w(getLog("start", "virtualDisplay is null"))
                state = State.ERROR
                onError(MjpegError.UnknownError(RuntimeException("virtualDisplay is null")))
                safeRelease()
            } else {
                state = State.STARTED
                XLog.d(getLog("start", "VirtualDisplay created: ${currentWidth}x${currentHeight}, fallback=$fallback"))
            }
        } catch (ex: SecurityException) {
            XLog.w(getLog("start", ex.toString()), ex)
            state = State.ERROR
            onError(MjpegError.CastSecurityException)
            safeRelease()
        }

        // Start timeout check for fallback (Quest 3 VR may not call onImageAvailable at all)
        if (state == State.STARTED && fallback.not()) {
            val startTime = System.currentTimeMillis()
            imageThreadHandler.postDelayed({
                synchronized(this@BitmapCapture) {
                    // If no frames received within 3 seconds and not yet in fallback mode, switch to fallback
                    if (state == State.STARTED && fallback.not() && lastImageMillis < startTime) {
                        XLog.d(getLog("start", "No frames received in 3s, switching to OpenGL ES fallback"))
                        fallback = true
                        restart()
                    }
                }
            }, 3000)
        }

        return state == State.STARTED
    }

    @Synchronized
    internal fun destroy() {
        XLog.d(getLog("destroy"))
        if (state == State.DESTROYED) {
            XLog.w(getLog("destroy", "Already destroyed"))
            return
        }
        coroutineScope.cancel()
        requireState(State.STARTED, State.ERROR)
        state = State.DESTROYED

        safeRelease()
        imageThread.quitSafely()
    }

    @Synchronized
    internal fun resize() {
        val metrics = getDisplayMetrics()
        resize(metrics.widthPixels, metrics.heightPixels)
    }

    @Synchronized
    internal fun resize(width: Int, height: Int) {
        XLog.d(getLog("resize", "Start (width: $width, height: $height)"))

        if (state != State.STARTED) {
            XLog.d(getLog("resize", "Ignored"))
            return
        }

        if (currentWidth == width && currentHeight == height) {
            XLog.i(getLog("resize", "Same width and height. Ignored"))
            return
        }

        currentWidth = width
        currentHeight = height

        virtualDisplay?.surface = null
        imageReader?.surface?.release() // For some reason imageReader.close() does not release surface
        imageReader?.close()

        val newImageListener = ImageListener()
        imageListener = newImageListener
        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2).apply {
            setOnImageAvailableListener(newImageListener, imageThreadHandler)
        }

        try {
            virtualDisplay?.resize(width, height, serviceContext.resources.configuration.densityDpi)
            virtualDisplay?.surface = imageReader!!.surface
        } catch (ex: SecurityException) {
            XLog.w(getLog("resize", ex.toString()), ex)
            state = State.ERROR
            onError(MjpegError.CastSecurityException)
            safeRelease()
        }

        reusableBitmap = null
        outputBitmap = null

        XLog.d(getLog("resize", "End"))
    }

    private fun safeRelease() {
        imageListener = null
        fallbackFrameListener = null
        virtualDisplay?.release()
        virtualDisplay = null
        imageReader?.surface?.release()
        imageReader?.close()
        imageReader = null
        
        // OpenGL ES resource cleanup
        mProducerSide?.release()
        mProducerSide = null
        mTexture?.release()
        mTexture = null
        mConsumerSide?.release()
        mConsumerSide = null
        mScreen = null
        mEglCore?.release()
        mEglCore = null
        mBuf = null
        
        reusableBitmap = null
        outputBitmap = null
    }
    @Synchronized
    private fun switchToFallback() {
        XLog.d(getLog("switchToFallback", "Switching to OpenGL ES fallback, size: ${currentWidth}x${currentHeight}"))
        if (state != State.STARTED) {
            XLog.d(getLog("switchToFallback", "Ignored, state=$state"))
            return
        }
        
        // Release ImageReader resources (but keep VirtualDisplay!)
        imageListener = null
        imageReader?.surface?.release()
        imageReader?.close()
        imageReader = null
        
        // Ensure resolution is capped to prevent overflow (Quest 3 has very high resolution)
        val maxRes = 1920
        val cappedWidth = min(currentWidth, maxRes)
        val cappedHeight = min(currentHeight, maxRes)
        
        // Calculate buffer size safely
        val bufferSize = cappedWidth.toLong() * cappedHeight.toLong() * 4
        if (bufferSize > Int.MAX_VALUE || bufferSize <= 0) {
            XLog.e(getLog("switchToFallback", "Buffer size overflow: $bufferSize"))
            state = State.ERROR
            onError(MjpegError.UnknownError(RuntimeException("Buffer size overflow: $bufferSize")))
            return
        }
        
        // Initialize OpenGL ES fallback with capped dimensions
        try {
            mEglCore = EglCore(null, EglCore.FLAG_TRY_GLES3 or EglCore.FLAG_RECORDABLE)
            mConsumerSide = OffscreenSurface(mEglCore, cappedWidth, cappedHeight)
            mConsumerSide!!.makeCurrent()

            val newFallbackListener = FallbackFrameListener(cappedWidth, cappedHeight)
            fallbackFrameListener = newFallbackListener
            mBuf = ByteBuffer.allocate(bufferSize.toInt()).apply { order(ByteOrder.nativeOrder()) }
            mScreen = FullFrameRect(Texture2dProgram(Texture2dProgram.ProgramType.TEXTURE_EXT))
            mTextureId = mScreen!!.createTextureObject()
            mTexture = SurfaceTexture(mTextureId, false).apply {
                setDefaultBufferSize(cappedWidth, cappedHeight)
                setOnFrameAvailableListener(newFallbackListener, imageThreadHandler)
            }
            mProducerSide = Surface(mTexture)
            
            mEglCore!!.makeNothingCurrent()
            
            // Swap the VirtualDisplay surface to OpenGL (Android 14+ compatible - no recreate!)
            virtualDisplay?.surface = mProducerSide
            
            XLog.d(getLog("switchToFallback", "Successfully switched to OpenGL ES surface"))
        } catch (cause: Throwable) {
            XLog.w(getLog("switchToFallback", "OpenGL ES fallback failed: ${cause.message}"), cause)
            state = State.ERROR
            onError(MjpegError.UnknownError(cause))
            safeRelease()
        }
    }
    
    @Synchronized
    private fun restart() {
        XLog.d(getLog("restart", "Start"))
        if (state != State.STARTED) {
            XLog.d(getLog("restart", "Ignored, state=$state"))
            return
        }
        // For fallback switching, use switchToFallback() instead
        if (fallback) {
            switchToFallback()
            return
        }
        safeRelease()
        state = State.INIT
        start()
        XLog.d(getLog("restart", "End"))
    }

    private inner class ImageListener : ImageReader.OnImageAvailableListener {
        override fun onImageAvailable(reader: ImageReader) {
            synchronized(this@BitmapCapture) {
                if (state != State.STARTED || this != imageListener || fallback) return

                var image: Image? = null
                try {
                    image = reader.acquireLatestImage() ?: return

                    val minTimeBetweenFramesMillis = when {
                        imageOptions.maxFPS > 0 -> 1000 / imageOptions.maxFPS.toLong()
                        imageOptions.maxFPS < 0 -> 1000 * abs(imageOptions.maxFPS.toLong()) // E-Link mode
                        else -> 0
                    }
                    val now = System.currentTimeMillis()
                    if (minTimeBetweenFramesMillis > 0 && now < lastImageMillis + minTimeBetweenFramesMillis) {
                        image.close()
                        return
                    }
                    lastImageMillis = now

                    val bitmap = transformImageToBitmap(image)
                    bitmapStateFlow.tryEmit(bitmap)

                } catch (ex: UnsupportedOperationException) {
                    // VR devices like Quest 3 may not support ImageReader format
                    // Switch to OpenGL ES fallback
                    XLog.d(this@BitmapCapture.getLog("onImageAvailable", "Unsupported format, switching to OpenGL ES fallback"))
                    fallback = true
                    restart()
                } catch (throwable: Throwable) {
                    XLog.e(this@BitmapCapture.getLog("onImageAvailable"), throwable)
                    state = State.ERROR
                    onError(MjpegError.BitmapCaptureException(throwable))
                    safeRelease()
                } finally {
                    image?.close()
                }
            }
        }
    }

    private fun transformImageToBitmap(image: Image): Bitmap {
        val plane = image.planes[0]
        val fullWidth = image.width
        val fullHeight = image.height

        val planeWidth = plane.rowStride / plane.pixelStride
        if (reusableBitmap == null || reusableBitmap!!.width != planeWidth || reusableBitmap!!.height != fullHeight) {
            reusableBitmap = createBitmap(planeWidth, fullHeight, Bitmap.Config.ARGB_8888)
        }
        reusableBitmap!!.copyPixelsFromBuffer(plane.buffer)

        val tmpBitmap = if (planeWidth > fullWidth) {
            Bitmap.createBitmap(reusableBitmap!!, 0, 0, fullWidth, fullHeight)
        } else {
            reusableBitmap!!
        }

        // VR Mode handling with IPD (Inter-Pupillary Distance) support
        // IPD offset in pixels: convert mm to approximate pixel offset based on screen density
        // Typical VR screen has ~10 pixels per mm at standard DPI
        val ipdOffsetPixels = (imageOptions.vrIpd - 64) * 10 / 2 // Offset from center based on IPD difference from default

        val vrLeft: Int
        val vrRight: Int
        when (imageOptions.vrMode) {
            MjpegSettings.Default.VR_MODE_LEFT -> {
                // Capture left half for left eye viewing
                vrLeft = 0
                vrRight = fullWidth / 2 + ipdOffsetPixels
            }
            MjpegSettings.Default.VR_MODE_RIGHT -> {
                // Capture right half for right eye viewing
                vrLeft = fullWidth / 2 - ipdOffsetPixels
                vrRight = fullWidth
            }
            MjpegSettings.Default.VR_MODE_STEREO -> {
                // Full stereo mode: output both eyes side-by-side (no crop, full width)
                vrLeft = 0
                vrRight = fullWidth
            }
            else -> {
                // VR_MODE_DISABLE: full screen
                vrLeft = 0
                vrRight = fullWidth
            }
        }

        var cropLeft = (vrLeft + imageOptions.cropLeft).coerceIn(0, fullWidth)
        var cropRight = (vrRight - imageOptions.cropRight).coerceIn(cropLeft, fullWidth)
        var cropTop = imageOptions.cropTop.coerceIn(0, fullHeight)
        var cropBottom = (fullHeight - imageOptions.cropBottom).coerceIn(cropTop, fullHeight)

        if (cropLeft >= cropRight || cropTop >= cropBottom) {
            cropLeft = vrLeft.coerceIn(0, fullWidth)
            cropTop = 0
            cropRight = vrRight.coerceIn(0, fullWidth)
            cropBottom = fullHeight // Fallback
        }

        val cropWidth = cropRight - cropLeft
        val cropHeight = cropBottom - cropTop

        val (scaleX, scaleY) = when {
            imageOptions.targetWidth > 0 && imageOptions.targetHeight > 0 -> {
                if (imageOptions.stretch) {
                    imageOptions.targetWidth.toFloat() / cropWidth to imageOptions.targetHeight.toFloat() / cropHeight
                } else {
                    min(imageOptions.targetWidth.toFloat() / cropWidth, imageOptions.targetHeight.toFloat() / cropHeight).let { it to it }
                }
            }

            imageOptions.resizeFactor != 100 -> {
                (imageOptions.resizeFactor / 100f).let { it to it }
            }

            else -> 1f to 1f
        }

        val scaledWidth = max(1, (cropWidth * scaleX).toInt())
        val scaledHeight = max(1, (cropHeight * scaleY).toInt())

        val rotated = imageOptions.rotationDegrees == 90 || imageOptions.rotationDegrees == 270
        val outputWidth = if (rotated) scaledHeight else scaledWidth
        val outputHeight = if (rotated) scaledWidth else scaledHeight

        if (transformMatrixDirty) {
            transformMatrix.apply {
                reset()
                setTranslate(-cropLeft.toFloat(), -cropTop.toFloat())
                postScale(scaleX, scaleY)
                postRotate(imageOptions.rotationDegrees.toFloat())
                when (imageOptions.rotationDegrees) {
                    90 -> postTranslate(scaledHeight.toFloat(), 0f)
                    180 -> postTranslate(scaledWidth.toFloat(), scaledHeight.toFloat())
                    270 -> postTranslate(0f, scaledWidth.toFloat())
                }
            }

            paint.colorFilter = if (imageOptions.grayscale) {
                ColorMatrixColorFilter(ColorMatrix().apply { setSaturation(0f) })
            } else null

            transformMatrixDirty = false
        }

        if (outputBitmap == null || outputBitmap!!.width != outputWidth || outputBitmap!!.height != outputHeight) {
            outputBitmap?.recycle()
            outputBitmap = createBitmap(outputWidth, outputHeight, Bitmap.Config.ARGB_8888)
        }

        val canvas = Canvas(outputBitmap!!)
        canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)
        canvas.drawBitmap(tmpBitmap, transformMatrix, paint)

        return outputBitmap!!.copy(outputBitmap!!.config ?: Bitmap.Config.ARGB_8888, false)
    }

    private fun getDisplayMetrics(): android.util.DisplayMetrics {
        val displayManager = serviceContext.getSystemService(Context.DISPLAY_SERVICE) as DisplayManager
        val display = displayManager.getDisplay(android.view.Display.DEFAULT_DISPLAY)
        val metrics = android.util.DisplayMetrics()
        display.getRealMetrics(metrics)
        return metrics
    }

    /** OpenGL ES fallback frame listener for VR devices (from v3.6.4)
     *  https://stackoverflow.com/a/34741581 **/
    private inner class FallbackFrameListener(
        private val width: Int, 
        private val height: Int
    ) : SurfaceTexture.OnFrameAvailableListener {
        override fun onFrameAvailable(surfaceTexture: SurfaceTexture?) {
            synchronized(this@BitmapCapture) {
                if (state != State.STARTED || this != fallbackFrameListener) return

                try {
                    mConsumerSide!!.makeCurrent()
                    mTexture!!.updateTexImage()

                    val minTimeBetweenFramesMillis = when {
                        imageOptions.maxFPS > 0 -> 1000 / imageOptions.maxFPS.toLong()
                        imageOptions.maxFPS < 0 -> 1000 * abs(imageOptions.maxFPS.toLong())
                        else -> 0
                    }
                    val now = System.currentTimeMillis()
                    if (minTimeBetweenFramesMillis > 0 && now < lastImageMillis + minTimeBetweenFramesMillis) {
                        return
                    }
                    lastImageMillis = now

                    FloatArray(16).let { matrix ->
                        mTexture!!.getTransformMatrix(matrix)
                        mScreen!!.drawFrame(mTextureId, matrix)
                    }

                    mConsumerSide!!.swapBuffers()

                    val buf = mBuf!!
                    buf.rewind()
                    GLES20.glReadPixels(0, 0, width, height, GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, buf)
                    buf.rewind()
                    
                    val cleanBitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                    cleanBitmap.copyPixelsFromBuffer(buf)

                    // Apply transformations similar to ImageListener
                    val bitmap = applyTransformations(cleanBitmap)
                    bitmapStateFlow.tryEmit(bitmap)

                } catch (throwable: Throwable) {
                    XLog.e(this@BitmapCapture.getLog("FallbackFrameListener"), throwable)
                    state = State.ERROR
                    onError(MjpegError.BitmapCaptureException(throwable))
                    safeRelease()
                }
            }
        }

        private fun applyTransformations(bitmap: Bitmap): Bitmap {
            // Simple transformation for fallback - just resize if needed
            val resizeFactor = imageOptions.resizeFactor
            if (resizeFactor < MjpegSettings.Values.RESIZE_DISABLED) {
                val scale = resizeFactor / 100f
                val newWidth = (bitmap.width * scale).toInt()
                val newHeight = (bitmap.height * scale).toInt()
                return Bitmap.createScaledBitmap(bitmap, newWidth, newHeight, true)
            }
            return bitmap
        }
    }
}