package info.dvkr.screenstream.input

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Path
import android.graphics.PixelFormat
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.SystemClock
import android.util.Log
import android.view.KeyEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.inputmethod.InputMethodManager
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.hardware.display.DisplayManager
import android.view.Display
import androidx.annotation.RequiresApi

/**
 * InputService - AccessibilityService for remote input control
 * 
 * Ported from droidVNC-NG's InputService.java
 * Provides touch, keyboard, and gesture injection via Android Accessibility API
 */
public class InputService : AccessibilityService() {

    public companion object {
        private const val TAG = "InputService"
        
        @Volatile
        public var instance: InputService? = null
            private set
        
        public var scaling: Float = 1.0f
        public var isInputEnabled: Boolean = true

        public var suppressSoftKeyboard: Boolean = false  // 默认关闭，让被控手机正常弹出键盘
        
        public fun isConnected(): Boolean = instance != null
    }

    // Per-client input state
    private var isButtonOneDown = false
    private val path = Path()
    private var stroke: GestureDescription.StrokeDescription? = null
    private var lastGestureStartTime: Long = 0

    private var imeOverlayView: View? = null
    private var imeHandler: Handler? = null
    
    // Keyboard modifier states
    private var isKeyCtrlDown = false
    private var isKeyAltDown = false
    private var isKeyShiftDown = false
    private var isKeyEscDown = false
    
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // We primarily use this service for input injection, not event monitoring
        // Debug logging disabled to avoid BuildConfig dependency issues
        // Log.d(TAG, "onAccessibilityEvent: $event")
    }

    override fun onInterrupt() {
        Log.w(TAG, "onInterrupt")
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i(TAG, "onServiceConnected - InputService is now active")

        imeHandler = Handler(mainLooper)
        setupImeOverlay()
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        removeImeOverlay()
        Log.i(TAG, "onDestroy - InputService stopped")
    }

    // ==================== Pointer Events ====================

    /**
     * Handle pointer/mouse events
     * @param buttonMask Bitmask of button states (1=left, 4=right, 8=scrollUp, 16=scrollDown)
     * @param x X coordinate
     * @param y Y coordinate
     */
    public fun onPointerEvent(buttonMask: Int, x: Int, y: Int) {
        if (!isInputEnabled) return

        val scaledX = (x / scaling).toInt()
        val scaledY = (y / scaling).toInt()

        // Left mouse button
        // Down, was up -> start stroke
        if ((buttonMask and 1) != 0 && !isButtonOneDown) {
            isButtonOneDown = true
            startStroke(scaledX, scaledY)
        }

        // Down, was down -> continue stroke
        if ((buttonMask and 1) != 0 && isButtonOneDown) {
            continueStroke(scaledX, scaledY)
        }

        // Up, was down -> end stroke
        if ((buttonMask and 1) == 0 && isButtonOneDown) {
            isButtonOneDown = false
            endStroke(scaledX, scaledY)
        }

        // Right mouse button -> long press
        if ((buttonMask and 4) != 0) {
            longPress(scaledX, scaledY)
        }

        // Scroll up
        if ((buttonMask and 8) != 0) {
            scroll(scaledX, scaledY, -500)
        }

        // Scroll down
        if ((buttonMask and 16) != 0) {
            scroll(scaledX, scaledY, 500)
        }
    }

    /**
     * Simple tap at coordinates
     */
    public fun tap(x: Int, y: Int) {
        val scaledX = (x / scaling).toInt()
        val scaledY = (y / scaling).toInt()
        dispatchClick(scaledX, scaledY, 100)
    }

    /**
     * Swipe from one point to another
     */
    /**
     * Swipe from one point to another
     */
    public fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long = 300) {
        val sx1 = (x1 / scaling).toInt()
        val sy1 = (y1 / scaling).toInt()
        val sx2 = (x2 / scaling).toInt()
        val sy2 = (y2 / scaling).toInt()
        
        performSwipe(sx1.toFloat(), sy1.toFloat(), sx2.toFloat(), sy2.toFloat(), durationMs)
    }

    /**
     * Tap at normalized coordinates (0.0 - 1.0)
     */
    /**
     * Tap at normalized coordinates (0.0 - 1.0)
     */
    public fun tapNormalized(nx: Float, ny: Float) {
        val (w, h) = getScreenResolution()
        val x = (nx * w).toInt().coerceIn(0, w - 1)
        val y = (ny * h).toInt().coerceIn(0, h - 1)
        dispatchClick(x, y, 100)
    }

    /**
     * Swipe at normalized coordinates (0.0 - 1.0)
     */
    public fun swipeNormalized(nx1: Float, ny1: Float, nx2: Float, ny2: Float, durationMs: Long = 300) {
        val (w, h) = getScreenResolution()
        val x1 = (nx1 * w).coerceIn(0f, (w - 1).toFloat())
        val y1 = (ny1 * h).coerceIn(0f, (h - 1).toFloat())
        val x2 = (nx2 * w).coerceIn(0f, (w - 1).toFloat())
        val y2 = (ny2 * h).coerceIn(0f, (h - 1).toFloat())
        performSwipe(x1, y1, x2, y2, durationMs)
    }

    private fun performSwipe(x1: Float, y1: Float, x2: Float, y2: Float, durationMs: Long) {
        val swipePath = Path().apply {
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val swipeStroke = GestureDescription.StrokeDescription(swipePath, 0, durationMs)
        val gesture = GestureDescription.Builder().addStroke(swipeStroke).build()
        dispatchGesture(gesture, null, null)
    }

    private fun getScreenResolution(): Pair<Int, Int> {
        val displayManager = getSystemService(Context.DISPLAY_SERVICE) as DisplayManager
        val display = displayManager.getDisplay(Display.DEFAULT_DISPLAY)
        
        val metrics = android.util.DisplayMetrics()
        // Use getRealMetrics to consistently get physical resolution, matching BitmapCapture logic
        // and avoiding potential scaling/compat issues with WindowMetrics in Service context
        @Suppress("DEPRECATION")
        display.getRealMetrics(metrics)
        
        val w = metrics.widthPixels
        val h = metrics.heightPixels
        

        return w to h
    }

    private fun startStroke(x: Int, y: Int) {
        path.reset()
        path.moveTo(x.toFloat(), y.toFloat())
        lastGestureStartTime = SystemClock.elapsedRealtime()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            stroke = null
        }
    }

    private fun continueStroke(x: Int, y: Int) {
        path.lineTo(x.toFloat(), y.toFloat())
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val currentTime = SystemClock.elapsedRealtime()
            var duration = currentTime - lastGestureStartTime
            if (duration == 0L) duration = 1

            stroke = if (stroke == null) {
                GestureDescription.StrokeDescription(path, 0, duration, true)
            } else {
                stroke!!.continueStroke(path, 0, duration, true)
            }

            dispatchStrokeAsGesture(stroke!!)
            lastGestureStartTime = currentTime
            path.reset()
            path.moveTo(x.toFloat(), y.toFloat())
        }
    }

    private fun endStroke(x: Int, y: Int) {
        path.lineTo(x.toFloat(), y.toFloat())
        var duration = SystemClock.elapsedRealtime() - lastGestureStartTime
        if (duration == 0L) duration = 1

        val finalStroke = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (stroke == null) {
                GestureDescription.StrokeDescription(path, 0, duration, false)
            } else {
                stroke!!.continueStroke(path, 0, duration, false)
            }
        } else {
            GestureDescription.StrokeDescription(path, 0, duration)
        }

        dispatchStrokeAsGesture(finalStroke)
    }

    private fun dispatchStrokeAsGesture(stroke: GestureDescription.StrokeDescription) {
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        dispatchGesture(gesture, null, null)
    }

    private fun longPress(x: Int, y: Int) {
        val duration = ViewConfiguration.getTapTimeout() + ViewConfiguration.getLongPressTimeout()
        dispatchClick(x, y, duration)
    }

    private fun scroll(x: Int, y: Int, scrollAmount: Int) {
        swipe(x, y, x, y - scrollAmount, ViewConfiguration.getScrollDefaultDelay().toLong())
    }

    private fun dispatchClick(x: Int, y: Int, durationMs: Int) {
        val clickPath = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val clickStroke = GestureDescription.StrokeDescription(clickPath, 0, durationMs.toLong())
        val gesture = GestureDescription.Builder().addStroke(clickStroke).build()
        dispatchGesture(gesture, null, null)

        scheduleHideSoftKeyboardIfNeeded()
    }

    private fun setupImeOverlay() {
        if (imeOverlayView != null) return
        try {
            val wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
            val view = View(this)
            val lp = WindowManager.LayoutParams(
                1,
                1,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT
            )
            wm.addView(view, lp)
            imeOverlayView = view
        } catch (e: Exception) {
            Log.w(TAG, "setupImeOverlay failed: ${e.message}")
        }
    }

    private fun removeImeOverlay() {
        val view = imeOverlayView ?: return
        try {
            val wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
            wm.removeView(view)
        } catch (_: Exception) {
        } finally {
            imeOverlayView = null
        }
    }

    private fun scheduleHideSoftKeyboardIfNeeded() {
        if (!suppressSoftKeyboard) return

        val focusNode = findFocusedNode() ?: return
        if (!focusNode.isEditable) return

        val handler = imeHandler ?: return
        handler.post { hideSoftKeyboard() }
        handler.postDelayed({ hideSoftKeyboard() }, 120)
        handler.postDelayed({ hideSoftKeyboard() }, 300)
    }

    private fun hideSoftKeyboard() {
        val view = imeOverlayView ?: return
        try {
            val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
            imm.hideSoftInputFromWindow(view.windowToken, 0)
        } catch (_: Exception) {
        }
    }

    // ==================== Key Events ====================

    /**
     * Handle keyboard events
     * @param down True if key pressed, false if released
     * @param keysym X11/RFB keysym value
     */
    public fun onKeyEvent(down: Boolean, keysym: Long) {
        if (!isInputEnabled) return

        // Track modifier states
        when (keysym) {
            0xFFE3L -> isKeyCtrlDown = down   // Ctrl
            0xFFE9L, 0xFF7EL -> isKeyAltDown = down  // Alt (Mac sends 0xFF7E)
            0xFFE1L -> isKeyShiftDown = down  // Shift
            0xFF1BL -> isKeyEscDown = down    // Escape
        }

        // Key combos
        if (isKeyCtrlDown && isKeyShiftDown && isKeyEscDown) {
            Log.i(TAG, "Ctrl-Shift-Esc: Recent Apps")
            performGlobalAction(GLOBAL_ACTION_RECENTS)
        }

        // Single key actions (on key down)
        if (down) {
            when (keysym) {
                0xFF08L -> {  // Backspace
                    Log.i(TAG, "Backspace key")
                    deleteLastChar()
                }
                0xFF50L -> {  // Home
                    Log.i(TAG, "Home key")
                    performGlobalAction(GLOBAL_ACTION_HOME)
                }
                0xFF57L -> {  // End -> Power dialog
                    Log.i(TAG, "End key -> Power dialog")
                    performGlobalAction(GLOBAL_ACTION_POWER_DIALOG)
                }
                0xFF1BL -> {  // Escape -> Back
                    Log.i(TAG, "Escape -> Back")
                    performGlobalAction(GLOBAL_ACTION_BACK)
                }
                0xFF6AL -> {  // XK_Select -> Select All
                    Log.i(TAG, "Select All")
                    selectAll()
                }
                0xFF63L -> {  // XK_Insert -> Copy
                    Log.i(TAG, "Copy")
                    copy()
                }
                0xFF6BL -> {  // XK_Cut
                    Log.i(TAG, "Cut")
                    cut()
                }
                0xFF6DL -> {  // XK_Paste (Custom mapping for robust Paste)
                    Log.i(TAG, "Paste command received")
                    paste()
                }
                0xFFFFL -> {  // Delete (restored)
                    Log.i(TAG, "Delete key")
                    deleteNextChar()
                }
            }
        }
    }

    /**
     * Global actions for navigation
     */
    public fun goHome() {
        performGlobalAction(GLOBAL_ACTION_HOME)
    }

    public fun goBack() {
        performGlobalAction(GLOBAL_ACTION_BACK)
    }

    public fun showRecents() {
        performGlobalAction(GLOBAL_ACTION_RECENTS)
    }

    public fun showNotifications() {
        performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
    }

    public fun showQuickSettings() {
        performGlobalAction(GLOBAL_ACTION_QUICK_SETTINGS)
    }

    // ==================== Text Input ====================

    /**
     * Input text into the currently focused field
     * Uses clipboard + paste to avoid interfering with autocomplete suggestions
     */
    public fun inputText(text: String) {
        if (!isInputEnabled) return

        try {
            val focusNode = findFocusedNode() ?: run {
                Log.w(TAG, "inputText: No focused node found")
                return
            }

            // Use clipboard + paste method to insert text without affecting autocomplete
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val originalClip = clipboard.primaryClip  // Save original clipboard
            
            // Set new text to clipboard and paste
            clipboard.setPrimaryClip(ClipData.newPlainText("input", text))
            focusNode.performAction(AccessibilityNodeInfo.ACTION_PASTE)
            
            // Restore original clipboard after a delay
            android.os.Handler(mainLooper).postDelayed({
                try {
                    if (originalClip != null) {
                        clipboard.setPrimaryClip(originalClip)
                    }
                } catch (e: Exception) {
                    // Ignore restore errors
                }
            }, 100)

            scheduleHideSoftKeyboardIfNeeded()
            
        } catch (e: Exception) {
            Log.e(TAG, "inputText failed: ${e.message}")
        }
    }

    /**
     * Set clipboard text
     */
    public fun setClipboard(text: String) {
        try {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            clipboard.setPrimaryClip(ClipData.newPlainText(text, text))
        } catch (e: Exception) {
            Log.e(TAG, "setClipboard failed: ${e.message}")
        }
    }

    private fun findFocusedNode(): AccessibilityNodeInfo? {
        return try {
            rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        } catch (e: Exception) {
            null
        }
    }

    // ==================== Text Editing Actions ====================

    /**
     * Delete the last character (Backspace)
     * When text becomes empty, explicitly clears the field to avoid autocomplete triggers
     */
    public fun deleteLastChar() {
        try {
            val focusNode = findFocusedNode() ?: return
            if (!focusNode.isEditable) return
            
            val currentText = focusNode.text?.toString() ?: ""
            
            if (currentText.isEmpty()) {
                // Text already empty - don't do anything that might trigger autocomplete
                // Just set empty text again to clear any pending suggestions
                val arguments = Bundle().apply {
                    putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, "")
                }
                focusNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)
                return
            }
            
            val newText = currentText.dropLast(1)
            val arguments = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
            }
            focusNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)
        } catch (e: Exception) {
            Log.e(TAG, "deleteLastChar failed: ${e.message}")
        }
    }

    /**
     * Delete the next character (Delete key)
     */
    public fun deleteNextChar() {
        // For simplicity, treat like backspace for now
        deleteLastChar()
    }

    /**
     * Select all text in the focused field
     */
    public fun selectAll() {
        try {
            val focusNode = findFocusedNode() ?: return
            val text = focusNode.text?.toString() ?: return
            if (text.isEmpty()) return
            
            val arguments = Bundle().apply {
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, 0)
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, text.length)
            }
            focusNode.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, arguments)
        } catch (e: Exception) {
            Log.e(TAG, "selectAll failed: ${e.message}")
        }
    }

    /**
     * Copy selected text to clipboard
     */
    public fun copy() {
        try {
            val focusNode = findFocusedNode() ?: return
            focusNode.performAction(AccessibilityNodeInfo.ACTION_COPY)
        } catch (e: Exception) {
            Log.e(TAG, "copy failed: ${e.message}")
        }
    }

    /**
     * Paste text from clipboard
     */
    public fun paste() {
        try {
            val focusNode = findFocusedNode() ?: return
            focusNode.performAction(AccessibilityNodeInfo.ACTION_PASTE)
        } catch (e: Exception) {
            Log.e(TAG, "paste failed: ${e.message}")
        }
    }

    /**
     * Cut selected text
     */
    public fun cut() {
        try {
            val focusNode = findFocusedNode() ?: return
            focusNode.performAction(AccessibilityNodeInfo.ACTION_CUT)
        } catch (e: Exception) {
            Log.e(TAG, "cut failed: ${e.message}")
        }
    }
}
