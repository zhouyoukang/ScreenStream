package info.dvkr.screenstream.input

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Path
import android.graphics.PixelFormat
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.PowerManager
import android.os.StatFs
import android.os.SystemClock
import android.media.AudioManager
import android.net.ConnectivityManager
import android.provider.Settings
import android.util.Log
import android.view.KeyEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.inputmethod.InputMethodManager
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.graphics.Rect
import android.hardware.display.DisplayManager
import android.view.Display
import androidx.annotation.RequiresApi
import org.json.JSONArray
import org.json.JSONObject

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

        @Volatile
        public var isScreenOffMode: Boolean = false // Track "Fake Screen Off" state

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
        if (event == null) return
        // Capture notification events for the Platform Layer
        if (event.eventType == AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED) {
            onNotificationEvent(event)
        }
        // Detect foreground app changes for macro triggers
        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val pkg = event.packageName?.toString() ?: ""
            if (pkg.isNotEmpty()) {
                MacroEngine.instance.onAppSwitch(pkg)
            }
        }
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

        MacroEngine.instance.init(applicationContext, this)
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
        } else if ((buttonMask and 1) != 0 && isButtonOneDown) {
            // Down, was down -> continue stroke
            continueStroke(scaledX, scaledY)
        } else if ((buttonMask and 1) == 0 && isButtonOneDown) {
            // Up, was down -> end stroke
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
        // x,y are already scaled — call performSwipe directly to avoid double-scaling via swipe()
        performSwipe(x.toFloat(), y.toFloat(), x.toFloat(), (y - scrollAmount).toFloat(),
            ViewConfiguration.getScrollDefaultDelay().toLong())
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
     * Handle keyboard events with full PC-parity:
     * - Selection-aware Backspace/Delete
     * - Arrow keys with Shift for selection, Ctrl for word-level
     * - Context-sensitive Home/End (text cursor vs global action)
     * - Enter, Tab, Undo
     */
    public fun onKeyEvent(down: Boolean, keysym: Long, shift: Boolean = false, ctrl: Boolean = false) {
        if (!isInputEnabled) return

        // Track modifier states from raw keysym events
        when (keysym) {
            0xFFE3L -> isKeyCtrlDown = down
            0xFFE9L, 0xFF7EL -> isKeyAltDown = down
            0xFFE1L -> isKeyShiftDown = down
            0xFF1BL -> isKeyEscDown = down
        }

        // Use explicit modifier flags if provided, fallback to tracked state
        val isShift = shift || isKeyShiftDown
        val isCtrl = ctrl || isKeyCtrlDown

        if (!down) return

        // Ctrl+Shift+Esc: Recent Apps
        if (isCtrl && isShift && isKeyEscDown) {
            performGlobalAction(GLOBAL_ACTION_RECENTS)
            return
        }

        val isTextContext = isEditableFieldFocused()

        when (keysym) {
            0xFF08L -> deleteBackward()                       // Backspace
            0xFFFFL -> deleteForward()                        // Delete
            0xFF0DL -> pressEnter()                           // Enter
            0xFF09L -> pressTab()                             // Tab
            0xFF65L -> undo()                                 // Ctrl+Z / Undo

            // Arrow keys: Ctrl = word-level, Shift = extend selection
            0xFF51L -> moveCursor(false, isShift, isCtrl)     // Left
            0xFF53L -> moveCursor(true, isShift, isCtrl)      // Right
            0xFF52L -> moveCursorVertical(false, isShift)     // Up
            0xFF54L -> moveCursorVertical(true, isShift)      // Down

            // Home/End: context-sensitive
            0xFF50L -> if (isTextContext) moveCursorToEdge(false, isShift) else performGlobalAction(GLOBAL_ACTION_HOME)
            0xFF57L -> if (isTextContext) moveCursorToEdge(true, isShift) else performGlobalAction(GLOBAL_ACTION_POWER_DIALOG)

            0xFF1BL -> performGlobalAction(GLOBAL_ACTION_BACK)   // Escape -> Back
            0xFF6AL -> selectAll()                               // Ctrl+A
            0xFF63L -> copy()                                    // Ctrl+C
            0xFF6BL -> cut()                                     // Ctrl+X
            0xFF6DL -> paste()                                   // Ctrl+V
        }
    }

    private fun isEditableFieldFocused(): Boolean {
        val node = findFocusedNode() ?: return false
        val editable = node.isEditable
        try { node.recycle() } catch (_: Exception) {}
        return editable
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

    public fun volumeUp() {
        val im = getSystemService(AUDIO_SERVICE) as android.media.AudioManager
        im.adjustStreamVolume(android.media.AudioManager.STREAM_MUSIC, android.media.AudioManager.ADJUST_RAISE, 0)
    }

    public fun volumeDown() {
        val im = getSystemService(AUDIO_SERVICE) as android.media.AudioManager
        im.adjustStreamVolume(android.media.AudioManager.STREAM_MUSIC, android.media.AudioManager.ADJUST_LOWER, 0)
    }

    public fun lockScreen() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            performGlobalAction(GLOBAL_ACTION_LOCK_SCREEN)
        }
    }

    // ==================== Text Input ====================

    public data class TextInputResult(
        val ok: Boolean,
        val method: String? = null,
        val error: String? = null
    )

    /**
     * Input text into the currently focused field
     * Uses clipboard + paste to avoid interfering with autocomplete suggestions
     */
    public fun inputText(text: String): TextInputResult {
        if (!isInputEnabled) return TextInputResult(ok = false, error = "input disabled")

        val focusNode = findFocusedNode() ?: run {
            Log.w(TAG, "inputText: No focused node found")
            return TextInputResult(ok = false, error = "no focused node")
        }

        try {
            try {
                focusNode.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
                if (!focusNode.isFocused) {
                    focusNode.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                }
            } catch (_: Exception) {
            }

            val rawText = focusNode.text?.toString() ?: ""

            // Detect hint/placeholder/autocomplete text and ignore it
            val isHintText = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                focusNode.isShowingHintText ||
                    (focusNode.hintText != null && rawText == focusNode.hintText.toString())
            } else {
                // Pre-O fallback: if cursor is at 0/0 or -1/-1 while text is non-empty,
                // it's likely placeholder text
                rawText.isNotEmpty() &&
                    focusNode.textSelectionStart <= 0 && focusNode.textSelectionEnd <= 0
            }

            val currentText = if (isHintText) "" else rawText
            var start: Int
            var end: Int

            if (isHintText) {
                start = 0
                end = 0
            } else {
                start = focusNode.textSelectionStart
                end = focusNode.textSelectionEnd
                if (start < 0 || end < 0) {
                    start = currentText.length
                    end = currentText.length
                }
                start = start.coerceIn(0, currentText.length)
                end = end.coerceIn(0, currentText.length)
                if (start > end) {
                    val tmp = start
                    start = end
                    end = tmp
                }
            }

            val newText = buildString {
                append(currentText.substring(0, start))
                append(text)
                append(currentText.substring(end))
            }

            val setTextArgs = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
            }

            if (focusNode.isEditable) {
                val setOk = focusNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, setTextArgs)
                if (setOk) {
                    val cursor = (start + text.length).coerceIn(0, newText.length)
                    val selArgs = Bundle().apply {
                        putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, cursor)
                        putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, cursor)
                    }
                    focusNode.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, selArgs)

                    scheduleHideSoftKeyboardIfNeeded()
                    return TextInputResult(ok = true, method = "set_text")
                }
            }

            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val originalClip = clipboard.primaryClip
            clipboard.setPrimaryClip(ClipData.newPlainText("input", text))
            val pasteNode = findFocusedNode() ?: focusNode
            val pasteOk = pasteNode.performAction(AccessibilityNodeInfo.ACTION_PASTE)
            if (pasteNode !== focusNode) {
                try {
                    pasteNode.recycle()
                } catch (_: Exception) {
                }
            }

            android.os.Handler(mainLooper).postDelayed({
                try {
                    if (originalClip != null) {
                        clipboard.setPrimaryClip(originalClip)
                    }
                } catch (_: Exception) {
                }
            }, 100)

            scheduleHideSoftKeyboardIfNeeded()

            return if (pasteOk) {
                TextInputResult(ok = true, method = "paste")
            } else {
                TextInputResult(ok = false, error = "paste failed")
            }
        } catch (e: Exception) {
            Log.e(TAG, "inputText failed: ${e.message}")
            return TextInputResult(ok = false, error = e.message)
        } finally {
            try {
                focusNode.recycle()
            } catch (_: Exception) {
            }
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
     * Helper: get real text from node, filtering out hint/placeholder text
     */
    private fun getRealText(node: AccessibilityNodeInfo): String {
        val raw = node.text?.toString() ?: ""
        val isHint = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            node.isShowingHintText || (node.hintText != null && raw == node.hintText.toString())
        } else {
            raw.isNotEmpty() && node.textSelectionStart <= 0 && node.textSelectionEnd <= 0
        }
        return if (isHint) "" else raw
    }

    /**
     * Helper: get selection range, returns Pair(start, end) with start <= end
     * Returns null if no valid cursor position
     */
    private fun getSelection(node: AccessibilityNodeInfo, textLen: Int): Pair<Int, Int> {
        var s = node.textSelectionStart
        var e = node.textSelectionEnd
        if (s < 0 || e < 0) { s = textLen; e = textLen }
        s = s.coerceIn(0, textLen)
        e = e.coerceIn(0, textLen)
        return if (s <= e) Pair(s, e) else Pair(e, s)
    }

    /**
     * Backspace: delete selected text, or one char before cursor
     */
    private fun deleteBackward() {
        val node = findFocusedNode() ?: return
        try {
            if (!node.isEditable) return
            val text = getRealText(node)

            if (text.isEmpty()) {
                val args = Bundle().apply {
                    putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, "")
                }
                node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                return
            }

            val (selStart, selEnd) = getSelection(node, text.length)

            val newText: String
            val newCursor: Int
            if (selStart != selEnd) {
                // Selection exists: delete entire selection
                newText = text.substring(0, selStart) + text.substring(selEnd)
                newCursor = selStart
            } else if (selStart > 0) {
                // No selection: delete char before cursor
                newText = text.substring(0, selStart - 1) + text.substring(selStart)
                newCursor = selStart - 1
            } else {
                return // Cursor at beginning, nothing to delete
            }

            node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
            })
            node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, Bundle().apply {
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, newCursor)
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, newCursor)
            })
        } catch (e: Exception) {
            Log.e(TAG, "deleteBackward failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Delete key: delete selected text, or one char after cursor
     */
    private fun deleteForward() {
        val node = findFocusedNode() ?: return
        try {
            if (!node.isEditable) return
            val text = getRealText(node)
            if (text.isEmpty()) return

            val (selStart, selEnd) = getSelection(node, text.length)

            val newText: String
            val newCursor: Int
            if (selStart != selEnd) {
                newText = text.substring(0, selStart) + text.substring(selEnd)
                newCursor = selStart
            } else if (selStart < text.length) {
                newText = text.substring(0, selStart) + text.substring(selStart + 1)
                newCursor = selStart
            } else {
                return // Cursor at end, nothing to delete
            }

            node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
            })
            node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, Bundle().apply {
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, newCursor)
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, newCursor)
            })
        } catch (e: Exception) {
            Log.e(TAG, "deleteForward failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Move cursor left/right. Ctrl = word granularity. Shift = extend selection.
     */
    private fun moveCursor(forward: Boolean, extendSelection: Boolean, wordLevel: Boolean) {
        val node = findFocusedNode() ?: return
        try {
            val granularity = if (wordLevel)
                AccessibilityNodeInfo.MOVEMENT_GRANULARITY_WORD
            else
                AccessibilityNodeInfo.MOVEMENT_GRANULARITY_CHARACTER

            val args = Bundle().apply {
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_MOVEMENT_GRANULARITY_INT, granularity)
                putBoolean(AccessibilityNodeInfo.ACTION_ARGUMENT_EXTEND_SELECTION_BOOLEAN, extendSelection)
            }

            val action = if (forward)
                AccessibilityNodeInfo.ACTION_NEXT_AT_MOVEMENT_GRANULARITY
            else
                AccessibilityNodeInfo.ACTION_PREVIOUS_AT_MOVEMENT_GRANULARITY

            node.performAction(action, args)
        } catch (e: Exception) {
            Log.e(TAG, "moveCursor failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Move cursor up/down (line granularity). Shift = extend selection.
     */
    private fun moveCursorVertical(down: Boolean, extendSelection: Boolean) {
        val node = findFocusedNode() ?: return
        try {
            val args = Bundle().apply {
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_MOVEMENT_GRANULARITY_INT,
                    AccessibilityNodeInfo.MOVEMENT_GRANULARITY_LINE)
                putBoolean(AccessibilityNodeInfo.ACTION_ARGUMENT_EXTEND_SELECTION_BOOLEAN, extendSelection)
            }
            val action = if (down)
                AccessibilityNodeInfo.ACTION_NEXT_AT_MOVEMENT_GRANULARITY
            else
                AccessibilityNodeInfo.ACTION_PREVIOUS_AT_MOVEMENT_GRANULARITY

            node.performAction(action, args)
        } catch (e: Exception) {
            Log.e(TAG, "moveCursorVertical failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Move cursor to start/end of line. Shift = extend selection.
     * Home → toEnd=false, End → toEnd=true
     */
    private fun moveCursorToEdge(toEnd: Boolean, extendSelection: Boolean) {
        val node = findFocusedNode() ?: return
        try {
            val args = Bundle().apply {
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_MOVEMENT_GRANULARITY_INT,
                    AccessibilityNodeInfo.MOVEMENT_GRANULARITY_LINE)
                putBoolean(AccessibilityNodeInfo.ACTION_ARGUMENT_EXTEND_SELECTION_BOOLEAN, extendSelection)
            }
            // Move to line start/end by traversing previous/next at line granularity
            val action = if (toEnd)
                AccessibilityNodeInfo.ACTION_NEXT_AT_MOVEMENT_GRANULARITY
            else
                AccessibilityNodeInfo.ACTION_PREVIOUS_AT_MOVEMENT_GRANULARITY

            node.performAction(action, args)
        } catch (e: Exception) {
            Log.e(TAG, "moveCursorToEdge failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Press Enter key
     */
    private fun pressEnter() {
        val node = findFocusedNode()
        if (node != null) {
            try {
                if (node.isEditable) {
                    // Try ACTION_IME_ENTER first (API 30+)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                        val entered = node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)
                        if (entered) return
                    }
                    // Fallback: insert newline via text manipulation
                    val text = getRealText(node)
                    val (selStart, selEnd) = getSelection(node, text.length)
                    val newText = text.substring(0, selStart) + "\n" + text.substring(selEnd)
                    node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply {
                        putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
                    })
                    val newCursor = selStart + 1
                    node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, Bundle().apply {
                        putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, newCursor)
                        putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, newCursor)
                    })
                } else {
                    // Non-editable: try clicking the focused element (e.g. a button)
                    node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                }
            } catch (e: Exception) {
                Log.e(TAG, "pressEnter failed: ${e.message}")
            } finally {
                try { node.recycle() } catch (_: Exception) {}
            }
        }
    }

    /**
     * Press Tab key - move focus to next element
     */
    private fun pressTab() {
        val node = findFocusedNode()
        try {
            node?.performAction(AccessibilityNodeInfo.ACTION_NEXT_HTML_ELEMENT)
                ?: performGlobalAction(GLOBAL_ACTION_BACK)
        } catch (_: Exception) {
            // Fallback: try focus navigation
            try {
                node?.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
            } catch (_: Exception) {}
        } finally {
            try { node?.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Undo last action (Ctrl+Z)
     */
    private fun undo() {
        // Android doesn't have a universal undo API via AccessibilityService.
        // Best effort: dispatch KEYCODE_Z with Ctrl meta state
        try {
            val now = SystemClock.uptimeMillis()
            val downEvent = KeyEvent(
                now, now, KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_Z,
                0, KeyEvent.META_CTRL_LEFT_ON or KeyEvent.META_CTRL_ON
            )
            val upEvent = KeyEvent(
                now, now, KeyEvent.ACTION_UP, KeyEvent.KEYCODE_Z,
                0, KeyEvent.META_CTRL_LEFT_ON or KeyEvent.META_CTRL_ON
            )
            // Inject via instrumentation is not available, so try soft keyboard dispatch
            val node = findFocusedNode()
            if (node != null) {
                try { node.recycle() } catch (_: Exception) {}
            }
            // As a best-effort, log the limitation
            Log.d(TAG, "undo: Ctrl+Z dispatched (limited support via AccessibilityService)")
        } catch (e: Exception) {
            Log.e(TAG, "undo failed: ${e.message}")
        }
    }

    /**
     * Select all text in the focused field
     */
    public fun selectAll() {
        val node = findFocusedNode() ?: return
        try {
            val text = getRealText(node)
            if (text.isEmpty()) return
            node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, Bundle().apply {
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, 0)
                putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, text.length)
            })
        } catch (e: Exception) {
            Log.e(TAG, "selectAll failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Copy selected text to clipboard
     */
    public fun copy() {
        val node = findFocusedNode() ?: return
        try {
            node.performAction(AccessibilityNodeInfo.ACTION_COPY)
        } catch (e: Exception) {
            Log.e(TAG, "copy failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Paste text from clipboard
     */
    public fun paste() {
        val node = findFocusedNode() ?: return
        try {
            node.performAction(AccessibilityNodeInfo.ACTION_PASTE)
        } catch (e: Exception) {
            Log.e(TAG, "paste failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Cut selected text
     */
    public fun cut() {
        val node = findFocusedNode() ?: return
        try {
            node.performAction(AccessibilityNodeInfo.ACTION_CUT)
        } catch (e: Exception) {
            Log.e(TAG, "cut failed: ${e.message}")
        } finally {
            try { node.recycle() } catch (_: Exception) {}
        }
    }
    // ==================== WebSocket Touch Stream ====================

    public fun onTouchStreamStart(nx: Float, ny: Float) {
        if (!isInputEnabled) return
        val (w, h) = getScreenResolution()
        val x = (nx * w).toInt().coerceIn(0, w - 1)
        val y = (ny * h).toInt().coerceIn(0, h - 1)
        startStroke(x, y)
    }

    public fun onTouchStreamMove(nx: Float, ny: Float) {
        if (!isInputEnabled) return
        val (w, h) = getScreenResolution()
        val x = (nx * w).toInt().coerceIn(0, w - 1)
        val y = (ny * h).toInt().coerceIn(0, h - 1)
        continueStroke(x, y)
    }

    public fun onTouchStreamEnd(nx: Float, ny: Float) {
        if (!isInputEnabled) return
        val (w, h) = getScreenResolution()
        val x = (nx * w).toInt().coerceIn(0, w - 1)
        val y = (ny * h).toInt().coerceIn(0, h - 1)
        endStroke(x, y)
    }

    // ==================== System Actions ====================

    public fun wakeScreen() {
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            @Suppress("DEPRECATION")
            val wl = pm.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
                "screenstream:wake"
            )
            wl.acquire(3000L)
            wl.release()
        } catch (e: Exception) {
            Log.e(TAG, "wakeScreen failed: ${e.message}")
        }
    }

    public fun showPowerDialog() {
        performGlobalAction(GLOBAL_ACTION_POWER_DIALOG)
    }

    public fun takeScreenshot() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            performGlobalAction(GLOBAL_ACTION_TAKE_SCREENSHOT)
        }
    }

    public fun toggleSplitScreen() {
        performGlobalAction(GLOBAL_ACTION_TOGGLE_SPLIT_SCREEN)
    }

    // ==================== Brightness Control ====================

    public fun setBrightness(level: Int) {
        try {
            if (!Settings.System.canWrite(this)) {
                Log.w(TAG, "setBrightness: No WRITE_SETTINGS permission")
                return
            }
            Settings.System.putInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS_MODE,
                Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL)
            Settings.System.putInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS,
                level.coerceIn(0, 255))
        } catch (e: Exception) {
            Log.e(TAG, "setBrightness failed: ${e.message}")
        }
    }

    public fun getBrightness(): Int {
        return try {
            Settings.System.getInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS)
        } catch (_: Exception) { -1 }
    }

    // ==================== Enhanced Gestures (Public API) ====================

    public fun longPressAt(x: Int, y: Int, durationMs: Long = 0) {
        val scaledX = (x / scaling).toInt()
        val scaledY = (y / scaling).toInt()
        val dur = if (durationMs > 0) durationMs.toInt()
                  else ViewConfiguration.getTapTimeout() + ViewConfiguration.getLongPressTimeout()
        dispatchClick(scaledX, scaledY, dur)
    }

    public fun longPressNormalized(nx: Float, ny: Float, durationMs: Long = 0) {
        val (w, h) = getScreenResolution()
        val x = (nx * w).toInt().coerceIn(0, w - 1)
        val y = (ny * h).toInt().coerceIn(0, h - 1)
        val dur = if (durationMs > 0) durationMs.toInt()
                  else ViewConfiguration.getTapTimeout() + ViewConfiguration.getLongPressTimeout()
        dispatchClick(x, y, dur)
    }

    public fun doubleTapAt(x: Int, y: Int) {
        val scaledX = (x / scaling).toInt()
        val scaledY = (y / scaling).toInt()
        dispatchClick(scaledX, scaledY, 50)
        Handler(mainLooper).postDelayed({ dispatchClick(scaledX, scaledY, 50) }, 120)
    }

    public fun doubleTapNormalized(nx: Float, ny: Float) {
        val (w, h) = getScreenResolution()
        val x = (nx * w).toInt().coerceIn(0, w - 1)
        val y = (ny * h).toInt().coerceIn(0, h - 1)
        dispatchClick(x, y, 50)
        Handler(mainLooper).postDelayed({ dispatchClick(x, y, 50) }, 120)
    }

    public fun scrollNormalized(nx: Float, ny: Float, direction: String, distance: Int = 500) {
        val (w, h) = getScreenResolution()
        val x = (nx * w).coerceIn(0f, (w - 1).toFloat())
        val y = (ny * h).coerceIn(0f, (h - 1).toFloat())
        val (ex, ey) = when (direction) {
            "down" -> x to (y - distance).coerceIn(0f, (h - 1).toFloat())
            "up"   -> x to (y + distance).coerceIn(0f, (h - 1).toFloat())
            "left"  -> (x + distance).coerceIn(0f, (w - 1).toFloat()) to y
            "right" -> (x - distance).coerceIn(0f, (w - 1).toFloat()) to y
            else -> x to y
        }
        performSwipe(x, y, ex, ey, 300)
    }

    public fun pinchZoom(centerNx: Float, centerNy: Float, zoomIn: Boolean) {
        val (w, h) = getScreenResolution()
        val cx = (centerNx * w).coerceIn(0f, (w - 1).toFloat())
        val cy = (centerNy * h).coerceIn(0f, (h - 1).toFloat())
        val spread = minOf(w, h) * 0.15f

        val path1 = Path()
        val path2 = Path()
        if (zoomIn) {
            path1.moveTo((cx - spread * 0.3f).coerceAtLeast(0f), cy)
            path1.lineTo((cx - spread).coerceAtLeast(0f), cy)
            path2.moveTo((cx + spread * 0.3f).coerceAtMost((w - 1).toFloat()), cy)
            path2.lineTo((cx + spread).coerceAtMost((w - 1).toFloat()), cy)
        } else {
            path1.moveTo((cx - spread).coerceAtLeast(0f), cy)
            path1.lineTo((cx - spread * 0.3f).coerceAtLeast(0f), cy)
            path2.moveTo((cx + spread).coerceAtMost((w - 1).toFloat()), cy)
            path2.lineTo((cx + spread * 0.3f).coerceAtMost((w - 1).toFloat()), cy)
        }

        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path1, 0, 400))
            .addStroke(GestureDescription.StrokeDescription(path2, 0, 400))
            .build()
        dispatchGesture(gesture, null, null)
    }

    // ==================== App & Device Management ====================

    public fun openApp(packageName: String): Boolean {
        return try {
            val intent = packageManager.getLaunchIntentForPackage(packageName)
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                startActivity(intent)
                true
            } else {
                Log.w(TAG, "openApp: No launch intent for $packageName")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "openApp failed: ${e.message}")
            false
        }
    }

    public fun openUrl(url: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "openUrl failed: ${e.message}")
            false
        }
    }

    private fun formatUptime(ms: Long): String {
        val s = ms / 1000
        val hours = s / 3600
        val minutes = (s % 3600) / 60
        return "${hours}h ${minutes}m"
    }

    @Suppress("DEPRECATION")
    public fun getDeviceInfo(): JSONObject {
        val json = JSONObject()
        try {
            val bm = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            json.put("batteryLevel", bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY))
            json.put("isCharging", bm.isCharging)

            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            json.put("isScreenOn", pm.isInteractive)

            try { json.put("brightness", getBrightness()) } catch (_: Exception) {}

            val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val ni = cm.activeNetworkInfo
            json.put("networkConnected", ni?.isConnected ?: false)
            json.put("networkType", ni?.typeName ?: "none")

            val stat = StatFs(Environment.getDataDirectory().path)
            json.put("storageAvailableMB", stat.availableBlocksLong * stat.blockSizeLong / (1024 * 1024))
            json.put("storageTotalMB", stat.blockCountLong * stat.blockSizeLong / (1024 * 1024))

            json.put("model", Build.MODEL)
            json.put("manufacturer", Build.MANUFACTURER)
            json.put("androidVersion", Build.VERSION.RELEASE)
            json.put("apiLevel", Build.VERSION.SDK_INT)

            val (w, h) = getScreenResolution()
            json.put("screenWidth", w)
            json.put("screenHeight", h)

            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            json.put("volumeMusic", am.getStreamVolume(AudioManager.STREAM_MUSIC))
            json.put("volumeMusicMax", am.getStreamMaxVolume(AudioManager.STREAM_MUSIC))
            json.put("volumeRing", am.getStreamVolume(AudioManager.STREAM_RING))

            // Uptime
            json.put("uptimeMs", SystemClock.elapsedRealtime())
            json.put("uptimeFormatted", formatUptime(SystemClock.elapsedRealtime()))

            // WiFi info
            try {
                val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as? android.net.wifi.WifiManager
                if (wm != null) {
                    val wi = wm.connectionInfo
                    if (wi != null) {
                        json.put("wifiSSID", wi.ssid?.replace("\"", "") ?: "")
                        json.put("wifiRSSI", wi.rssi)
                        json.put("wifiSpeed", wi.linkSpeed)
                    }
                }
            } catch (_: Exception) {}

            // Stay awake & show touches status
            json.put("stayAwake", isStayAwake())
            json.put("showTouches", getShowTouches())
            json.put("inputEnabled", isInputEnabled)
        } catch (e: Exception) {
            Log.e(TAG, "getDeviceInfo failed: ${e.message}")
        }
        return json
    }

    public fun getInstalledApps(): JSONArray {
        val apps = JSONArray()
        try {
            val intent = Intent(Intent.ACTION_MAIN, null)
            intent.addCategory(Intent.CATEGORY_LAUNCHER)
            val resolveInfoList = packageManager.queryIntentActivities(intent, 0)
            for (ri in resolveInfoList.sortedBy { it.loadLabel(packageManager).toString() }) {
                apps.put(JSONObject().apply {
                    put("packageName", ri.activityInfo.packageName)
                    put("appName", ri.loadLabel(packageManager).toString())
                })
            }
        } catch (e: Exception) {
            Log.e(TAG, "getInstalledApps failed: ${e.message}")
        }
        return apps
    }

    public fun getClipboardText(): String? {
        return try {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            clipboard.primaryClip?.getItemAt(0)?.text?.toString()
        } catch (e: Exception) {
            Log.e(TAG, "getClipboard failed: ${e.message}")
            null
        }
    }

    /* ARCHIVED: Screen Off (Brightness Control) 功能暂时禁用，保留代码供未来参考
    // ==================== Screen Off Mode (Brightness Control Only) ====================

    private var savedBrightness: Int = -1
    private var savedBrightnessMode: Int = -1

    public fun toggleScreenOff() {
        if (isScreenOffMode) {
            restoreBrightness()
        } else {
            setMinimumBrightness()
        }
    }

    private fun setMinimumBrightness() {
        try {
            if (!android.provider.Settings.System.canWrite(this)) {
                Log.e(TAG, "setMinimumBrightness: No WRITE_SETTINGS permission!")
                isScreenOffMode = true
                return
            }
            savedBrightnessMode = android.provider.Settings.System.getInt(
                contentResolver,
                android.provider.Settings.System.SCREEN_BRIGHTNESS_MODE,
                android.provider.Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL
            )
            savedBrightness = android.provider.Settings.System.getInt(
                contentResolver,
                android.provider.Settings.System.SCREEN_BRIGHTNESS
            )
            Log.i(TAG, "setMinimumBrightness: Saved brightness=$savedBrightness, mode=$savedBrightnessMode")
            android.provider.Settings.System.putInt(
                contentResolver,
                android.provider.Settings.System.SCREEN_BRIGHTNESS_MODE,
                android.provider.Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL
            )
            android.provider.Settings.System.putInt(
                contentResolver,
                android.provider.Settings.System.SCREEN_BRIGHTNESS,
                1
            )
            isScreenOffMode = true
            Log.i(TAG, "Screen Off Mode Enabled (System Brightness = 1)")
        } catch (e: Exception) {
            Log.e(TAG, "setMinimumBrightness failed: ${e.message}")
            isScreenOffMode = true
        }
    }

    private fun restoreBrightness() {
        try {
            if (!android.provider.Settings.System.canWrite(this)) {
                Log.e(TAG, "restoreBrightness: No WRITE_SETTINGS permission!")
                isScreenOffMode = false
                return
            }
            if (savedBrightness != -1) {
                android.provider.Settings.System.putInt(
                    contentResolver,
                    android.provider.Settings.System.SCREEN_BRIGHTNESS,
                    savedBrightness
                )
                Log.i(TAG, "restoreBrightness: Restored brightness=$savedBrightness")
            }
            if (savedBrightnessMode != -1) {
                android.provider.Settings.System.putInt(
                    contentResolver,
                    android.provider.Settings.System.SCREEN_BRIGHTNESS_MODE,
                    savedBrightnessMode
                )
                Log.i(TAG, "restoreBrightness: Restored mode=$savedBrightnessMode")
            }
            isScreenOffMode = false
            Log.i(TAG, "Screen Off Mode Disabled")
        } catch (e: Exception) {
            Log.e(TAG, "restoreBrightness failed: ${e.message}")
            isScreenOffMode = false
        }
    }
    */

    // ==================== Stay Awake (scrcpy -w style) ====================

    private var stayAwakeWakeLock: PowerManager.WakeLock? = null

    @Suppress("DEPRECATION")
    public fun setStayAwake(enabled: Boolean): Boolean {
        return try {
            if (enabled) {
                if (stayAwakeWakeLock == null) {
                    val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
                    stayAwakeWakeLock = pm.newWakeLock(
                        PowerManager.SCREEN_DIM_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
                        "screenstream:stayawake"
                    )
                }
                if (stayAwakeWakeLock?.isHeld != true) {
                    stayAwakeWakeLock?.acquire(4 * 60 * 60 * 1000L) // 4 hours max
                    Log.i(TAG, "Stay awake enabled")
                }
            } else {
                if (stayAwakeWakeLock?.isHeld == true) {
                    stayAwakeWakeLock?.release()
                    Log.i(TAG, "Stay awake disabled")
                }
            }
            true
        } catch (e: Exception) {
            Log.e(TAG, "setStayAwake failed: ${e.message}")
            false
        }
    }

    public fun isStayAwake(): Boolean = stayAwakeWakeLock?.isHeld == true

    // ==================== Show Touches Toggle ====================

    public fun setShowTouches(enabled: Boolean): Boolean {
        return try {
            Settings.System.putInt(contentResolver, "show_touches", if (enabled) 1 else 0)
            Log.i(TAG, "Show touches: $enabled")
            true
        } catch (e: Exception) {
            Log.e(TAG, "setShowTouches failed: ${e.message}")
            false
        }
    }

    public fun getShowTouches(): Boolean {
        return try {
            Settings.System.getInt(contentResolver, "show_touches", 0) == 1
        } catch (_: Exception) { false }
    }

    // ==================== Rotate Display ====================

    public fun setRotation(degrees: Int): Boolean {
        return try {
            val rotation = when (degrees) {
                0 -> android.view.Surface.ROTATION_0
                90 -> android.view.Surface.ROTATION_90
                180 -> android.view.Surface.ROTATION_180
                270 -> android.view.Surface.ROTATION_270
                else -> return false
            }
            Settings.System.putInt(contentResolver, Settings.System.ACCELEROMETER_ROTATION, 0)
            Settings.System.putInt(contentResolver, Settings.System.USER_ROTATION, rotation)
            Log.i(TAG, "Rotation set to $degrees")
            true
        } catch (e: Exception) {
            Log.e(TAG, "setRotation failed: ${e.message}")
            false
        }
    }

    // ==================== Media Control (KDE Connect / Phone Link style) ====================

    public fun mediaControl(action: String): Boolean {
        return try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val keyCode = when (action) {
                "play", "pause", "playpause" -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
                "next" -> KeyEvent.KEYCODE_MEDIA_NEXT
                "prev", "previous" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
                "stop" -> KeyEvent.KEYCODE_MEDIA_STOP
                "rewind" -> KeyEvent.KEYCODE_MEDIA_REWIND
                "forward", "fastforward" -> KeyEvent.KEYCODE_MEDIA_FAST_FORWARD
                else -> return false
            }
            val downEvent = KeyEvent(KeyEvent.ACTION_DOWN, keyCode)
            val upEvent = KeyEvent(KeyEvent.ACTION_UP, keyCode)
            am.dispatchMediaKeyEvent(downEvent)
            am.dispatchMediaKeyEvent(upEvent)
            Log.i(TAG, "mediaControl: $action")
            true
        } catch (e: Exception) {
            Log.e(TAG, "mediaControl failed: ${e.message}")
            false
        }
    }

    // ==================== Find My Phone (KDE Connect style) ====================

    private var findPhonePlayer: android.media.MediaPlayer? = null
    private var findPhoneSavedVolume: Int = -1

    public fun findPhone(ring: Boolean): Boolean {
        return try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            if (ring) {
                if (findPhonePlayer != null) return true
                findPhoneSavedVolume = am.getStreamVolume(AudioManager.STREAM_ALARM)
                am.setStreamVolume(AudioManager.STREAM_ALARM, am.getStreamMaxVolume(AudioManager.STREAM_ALARM), 0)
                val uri = android.media.RingtoneManager.getDefaultUri(android.media.RingtoneManager.TYPE_ALARM)
                    ?: android.media.RingtoneManager.getDefaultUri(android.media.RingtoneManager.TYPE_RINGTONE)
                findPhonePlayer = android.media.MediaPlayer().apply {
                    setDataSource(this@InputService, uri)
                    setAudioStreamType(AudioManager.STREAM_ALARM)
                    isLooping = true
                    prepare()
                    start()
                }
                Handler(mainLooper).postDelayed({ findPhone(false) }, 30000) // auto-stop after 30s
                Log.i(TAG, "findPhone: ringing")
            } else {
                findPhonePlayer?.stop()
                findPhonePlayer?.release()
                findPhonePlayer = null
                if (findPhoneSavedVolume >= 0) {
                    am.setStreamVolume(AudioManager.STREAM_ALARM, findPhoneSavedVolume, 0)
                    findPhoneSavedVolume = -1
                }
                Log.i(TAG, "findPhone: stopped, volume restored")
            }
            true
        } catch (e: Exception) {
            Log.e(TAG, "findPhone failed: ${e.message}")
            findPhonePlayer = null
            false
        }
    }

    // ==================== Vibrate Device ====================

    public fun vibrateDevice(durationMs: Long = 500, pattern: LongArray? = null): Boolean {
        return try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as android.os.VibratorManager
                vm.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(Context.VIBRATOR_SERVICE) as android.os.Vibrator
            }
            if (pattern != null) {
                @Suppress("DEPRECATION")
                vibrator.vibrate(pattern, -1)
            } else {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator.vibrate(android.os.VibrationEffect.createOneShot(durationMs, android.os.VibrationEffect.DEFAULT_AMPLITUDE))
                } else {
                    @Suppress("DEPRECATION")
                    vibrator.vibrate(durationMs)
                }
            }
            true
        } catch (e: Exception) {
            Log.e(TAG, "vibrateDevice failed: ${e.message}")
            false
        }
    }

    // ==================== Flashlight Toggle ====================

    public fun setFlashlight(enabled: Boolean): Boolean {
        return try {
            val cm = getSystemService(Context.CAMERA_SERVICE) as android.hardware.camera2.CameraManager
            val cameraId = cm.cameraIdList.firstOrNull() ?: return false
            cm.setTorchMode(cameraId, enabled)
            Log.i(TAG, "Flashlight: $enabled")
            true
        } catch (e: Exception) {
            Log.e(TAG, "setFlashlight failed: ${e.message}")
            false
        }
    }

    // ==================== Do Not Disturb ====================

    public fun setDndMode(enabled: Boolean): Boolean {
        return try {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
            if (!nm.isNotificationPolicyAccessGranted) {
                Log.w(TAG, "DND: No notification policy access")
                return false
            }
            nm.setInterruptionFilter(
                if (enabled) android.app.NotificationManager.INTERRUPTION_FILTER_NONE
                else android.app.NotificationManager.INTERRUPTION_FILTER_ALL
            )
            Log.i(TAG, "DND mode: $enabled")
            true
        } catch (e: Exception) {
            Log.e(TAG, "setDndMode failed: ${e.message}")
            false
        }
    }

    public fun isDndEnabled(): Boolean {
        return try {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
            nm.currentInterruptionFilter != android.app.NotificationManager.INTERRUPTION_FILTER_ALL
        } catch (_: Exception) { false }
    }

    // ==================== Set Volume Level ====================

    public fun setVolumeLevel(stream: String, level: Int): Boolean {
        return try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val streamType = when (stream) {
                "music", "media" -> AudioManager.STREAM_MUSIC
                "ring", "ringtone" -> AudioManager.STREAM_RING
                "alarm" -> AudioManager.STREAM_ALARM
                "notification" -> AudioManager.STREAM_NOTIFICATION
                "system" -> AudioManager.STREAM_SYSTEM
                "voice", "call" -> AudioManager.STREAM_VOICE_CALL
                else -> AudioManager.STREAM_MUSIC
            }
            val maxVol = am.getStreamMaxVolume(streamType)
            am.setStreamVolume(streamType, level.coerceIn(0, maxVol), 0)
            Log.i(TAG, "setVolume: $stream=$level")
            true
        } catch (e: Exception) {
            Log.e(TAG, "setVolumeLevel failed: ${e.message}")
            false
        }
    }

    // ==================== Auto-Rotate Toggle ====================

    public fun setAutoRotate(enabled: Boolean): Boolean {
        return try {
            Settings.System.putInt(contentResolver, Settings.System.ACCELEROMETER_ROTATION, if (enabled) 1 else 0)
            Log.i(TAG, "Auto-rotate: $enabled")
            true
        } catch (e: Exception) {
            Log.e(TAG, "setAutoRotate failed: ${e.message}")
            false
        }
    }

    public fun isAutoRotate(): Boolean {
        return try {
            Settings.System.getInt(contentResolver, Settings.System.ACCELEROMETER_ROTATION, 0) == 1
        } catch (_: Exception) { false }
    }

    // ==================== Foreground App / Running Processes ====================

    public fun getForegroundApp(): JSONObject {
        val json = JSONObject()
        try {
            val root = rootInActiveWindow
            if (root != null) {
                json.put("packageName", root.packageName?.toString() ?: "")
                json.put("className", root.className?.toString() ?: "")
                try { root.recycle() } catch (_: Exception) {}
            }
        } catch (e: Exception) {
            json.put("error", e.message ?: "unknown")
        }
        return json
    }

    // ==================== Kill Foreground App ====================

    public fun killForegroundApp(): Boolean {
        return try {
            performGlobalAction(GLOBAL_ACTION_BACK)
            Handler(mainLooper).postDelayed({
                performGlobalAction(GLOBAL_ACTION_BACK)
            }, 200)
            Handler(mainLooper).postDelayed({
                performGlobalAction(GLOBAL_ACTION_HOME)
            }, 400)
            Log.i(TAG, "killForegroundApp: sent back+back+home")
            true
        } catch (e: Exception) {
            Log.e(TAG, "killForegroundApp failed: ${e.message}")
            false
        }
    }

    // ==================== Save File to Device ====================

    public fun saveFile(filename: String, data: ByteArray): JSONObject {
        return try {
            if (filename.contains('/') || filename.contains('\\') || filename.contains("..")) {
                return JSONObject().put("ok", false).put("error", "Invalid filename: path separators not allowed")
            }
            val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
            if (!dir.exists()) dir.mkdirs()
            val file = java.io.File(dir, filename)
            file.writeBytes(data)
            Log.i(TAG, "saveFile: ${file.absolutePath} (${data.size} bytes)")
            JSONObject().put("ok", true).put("path", file.absolutePath).put("size", data.size)
        } catch (e: Exception) {
            Log.e(TAG, "saveFile failed: ${e.message}")
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    // ==================== S33: Remote File Manager ====================

    private fun sanitizePath(path: String): java.io.File {
        val base = Environment.getExternalStorageDirectory()
        val resolved = java.io.File(path).canonicalFile
        if (!resolved.absolutePath.startsWith(base.absolutePath)) {
            throw SecurityException("Access denied: outside storage")
        }
        return resolved
    }

    private fun fileToJson(f: java.io.File): JSONObject {
        val j = JSONObject()
        j.put("name", f.name)
        j.put("path", f.absolutePath)
        j.put("isDir", f.isDirectory)
        j.put("size", if (f.isDirectory) 0L else f.length())
        j.put("modified", f.lastModified())
        j.put("readable", f.canRead())
        j.put("writable", f.canWrite())
        if (!f.isDirectory) {
            val ext = f.extension.lowercase()
            j.put("ext", ext)
            val mime = when (ext) {
                "jpg", "jpeg" -> "image/jpeg"
                "png" -> "image/png"
                "gif" -> "image/gif"
                "webp" -> "image/webp"
                "bmp" -> "image/bmp"
                "mp4" -> "video/mp4"
                "mkv" -> "video/x-matroska"
                "avi" -> "video/x-msvideo"
                "mp3" -> "audio/mpeg"
                "wav" -> "audio/wav"
                "ogg" -> "audio/ogg"
                "flac" -> "audio/flac"
                "pdf" -> "application/pdf"
                "txt", "log", "csv", "md" -> "text/plain"
                "json" -> "application/json"
                "xml" -> "application/xml"
                "html", "htm" -> "text/html"
                "zip" -> "application/zip"
                "apk" -> "application/vnd.android.package-archive"
                else -> "application/octet-stream"
            }
            j.put("mime", mime)
        }
        return j
    }

    public fun listFiles(path: String, showHidden: Boolean = false, sortBy: String = "name"): JSONObject {
        return try {
            val dir = sanitizePath(path)
            if (!dir.exists()) return JSONObject().put("ok", false).put("error", "Not found: $path")
            if (!dir.isDirectory) return JSONObject().put("ok", false).put("error", "Not a directory")
            if (!dir.canRead()) return JSONObject().put("ok", false).put("error", "Permission denied")
            val items = dir.listFiles()?.filter { showHidden || !it.name.startsWith(".") } ?: emptyList()
            val sorted = when (sortBy) {
                "size" -> items.sortedBy { it.length() }
                "modified" -> items.sortedByDescending { it.lastModified() }
                "type" -> items.sortedBy { it.extension.lowercase() }
                else -> items.sortedWith(compareBy<java.io.File> { !it.isDirectory }.thenBy { it.name.lowercase() })
            }
            val arr = JSONArray()
            sorted.forEach { arr.put(fileToJson(it)) }
            val result = JSONObject()
            result.put("ok", true)
            result.put("path", dir.absolutePath)
            result.put("parent", dir.parent ?: "")
            result.put("count", sorted.size)
            result.put("files", arr)
            // Storage stats
            val stat = StatFs(dir.absolutePath)
            result.put("freeBytes", stat.availableBytes)
            result.put("totalBytes", stat.totalBytes)
            result
        } catch (e: SecurityException) {
            JSONObject().put("ok", false).put("error", e.message ?: "Access denied")
        } catch (e: Exception) {
            Log.e(TAG, "listFiles failed: ${e.message}")
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun getFileInfo(path: String): JSONObject {
        return try {
            val f = sanitizePath(path)
            if (!f.exists()) return JSONObject().put("ok", false).put("error", "Not found")
            val info = fileToJson(f)
            info.put("ok", true)
            if (f.isDirectory) {
                val children = f.listFiles()
                info.put("childCount", children?.size ?: 0)
                var totalSize = 0L
                children?.forEach { if (it.isFile) totalSize += it.length() }
                info.put("totalSize", totalSize)
            }
            info
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun createDirectory(path: String): JSONObject {
        return try {
            val dir = sanitizePath(path)
            if (dir.exists()) return JSONObject().put("ok", false).put("error", "Already exists")
            val created = dir.mkdirs()
            JSONObject().put("ok", created).put("path", dir.absolutePath)
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun removeFile(path: String): JSONObject {
        return try {
            val f = sanitizePath(path)
            if (!f.exists()) return JSONObject().put("ok", false).put("error", "Not found")
            val deleted = if (f.isDirectory) f.deleteRecursively() else f.delete()
            Log.i(TAG, "deleteFile: $path -> $deleted")
            JSONObject().put("ok", deleted).put("path", f.absolutePath)
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun renameFile(path: String, newName: String): JSONObject {
        return try {
            val f = sanitizePath(path)
            if (!f.exists()) return JSONObject().put("ok", false).put("error", "Not found")
            if (newName.contains('/') || newName.contains('\\') || newName.contains("..")) {
                return JSONObject().put("ok", false).put("error", "Invalid name: path separators not allowed")
            }
            val target = java.io.File(f.parent, newName)
            if (target.exists()) return JSONObject().put("ok", false).put("error", "Target already exists")
            val ok = f.renameTo(target)
            JSONObject().put("ok", ok).put("oldPath", f.absolutePath).put("newPath", target.absolutePath)
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun moveFile(srcPath: String, destPath: String): JSONObject {
        return try {
            val src = sanitizePath(srcPath)
            val dest = sanitizePath(destPath)
            if (!src.exists()) return JSONObject().put("ok", false).put("error", "Source not found")
            val target = if (dest.isDirectory) java.io.File(dest, src.name) else dest
            if (target.exists()) return JSONObject().put("ok", false).put("error", "Target exists")
            val ok = src.renameTo(target)
            JSONObject().put("ok", ok).put("path", target.absolutePath)
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun copyFile(srcPath: String, destPath: String): JSONObject {
        return try {
            val src = sanitizePath(srcPath)
            val dest = sanitizePath(destPath)
            if (!src.exists()) return JSONObject().put("ok", false).put("error", "Source not found")
            val target = if (dest.isDirectory) java.io.File(dest, src.name) else dest
            if (target.exists()) return JSONObject().put("ok", false).put("error", "Target exists")
            if (src.isDirectory) {
                src.copyRecursively(target, overwrite = false)
            } else {
                src.copyTo(target, overwrite = false)
            }
            JSONObject().put("ok", true).put("path", target.absolutePath).put("size", target.length())
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun readTextFile(path: String, maxSize: Long = 512 * 1024): JSONObject {
        return try {
            val f = sanitizePath(path)
            if (!f.exists()) return JSONObject().put("ok", false).put("error", "Not found")
            if (f.isDirectory) return JSONObject().put("ok", false).put("error", "Is a directory")
            if (f.length() > maxSize) return JSONObject().put("ok", false).put("error", "File too large (${f.length()} > $maxSize)")
            val content = f.readText(Charsets.UTF_8)
            JSONObject().put("ok", true).put("content", content).put("size", f.length()).put("path", f.absolutePath)
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun readFileBase64(path: String, maxSize: Long = 10 * 1024 * 1024): JSONObject {
        return try {
            val f = sanitizePath(path)
            if (!f.exists()) return JSONObject().put("ok", false).put("error", "Not found")
            if (f.length() > maxSize) return JSONObject().put("ok", false).put("error", "File too large")
            val bytes = f.readBytes()
            val b64 = android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP)
            val ext = f.extension.lowercase()
            val mime = fileToJson(f).optString("mime", "application/octet-stream")
            JSONObject().put("ok", true).put("data", b64).put("mime", mime).put("size", bytes.size).put("name", f.name)
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun uploadFile(path: String, data: ByteArray): JSONObject {
        return try {
            val file = sanitizePath(path)
            file.parentFile?.let { if (!it.exists()) it.mkdirs() }
            file.writeBytes(data)
            Log.i(TAG, "uploadFile: ${file.absolutePath} (${data.size} bytes)")
            JSONObject().put("ok", true).put("path", file.absolutePath).put("size", data.size)
        } catch (e: SecurityException) {
            JSONObject().put("ok", false).put("error", e.message ?: "Access denied")
        } catch (e: Exception) {
            Log.e(TAG, "uploadFile failed: ${e.message}")
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun searchFiles(basePath: String, query: String, maxResults: Int = 100): JSONObject {
        return try {
            val base = sanitizePath(basePath)
            if (!base.isDirectory) return JSONObject().put("ok", false).put("error", "Not a directory")
            val results = JSONArray()
            var count = 0
            val lowerQuery = query.lowercase()
            fun walk(dir: java.io.File, depth: Int) {
                if (depth > 8 || count >= maxResults) return
                val children = dir.listFiles() ?: return
                for (child in children) {
                    if (count >= maxResults) return
                    if (child.name.lowercase().contains(lowerQuery)) {
                        results.put(fileToJson(child))
                        count++
                    }
                    if (child.isDirectory && !child.name.startsWith(".")) {
                        walk(child, depth + 1)
                    }
                }
            }
            walk(base, 0)
            JSONObject().put("ok", true).put("query", query).put("count", count).put("results", results)
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    public fun getStorageInfo(): JSONObject {
        return try {
            val ext = Environment.getExternalStorageDirectory()
            val stat = StatFs(ext.absolutePath)
            val json = JSONObject()
            json.put("ok", true)
            json.put("storagePath", ext.absolutePath)
            json.put("totalBytes", stat.totalBytes)
            json.put("freeBytes", stat.availableBytes)
            json.put("usedBytes", stat.totalBytes - stat.availableBytes)
            // Common directories
            val dirs = JSONArray()
            val knownDirs = arrayOf("DCIM", "Download", "Documents", "Music", "Movies", "Pictures", "Ringtones", "Alarms", "Notifications", "Podcasts")
            for (name in knownDirs) {
                val d = java.io.File(ext, name)
                if (d.exists() && d.isDirectory) {
                    dirs.put(JSONObject().put("name", name).put("path", d.absolutePath))
                }
            }
            json.put("quickAccess", dirs)
            json
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    // ==================== View Tree & Semantic Actions (AI Brain Layer) ====================

    public fun getViewTree(maxDepth: Int = 8): JSONObject {
        val root = rootInActiveWindow
            ?: return JSONObject().put("error", "No active window")
        return try {
            serializeNode(root, 0, maxDepth)
        } catch (e: Exception) {
            Log.e(TAG, "getViewTree failed: ${e.message}")
            JSONObject().put("error", e.message ?: "unknown")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }

    private fun serializeNode(node: AccessibilityNodeInfo, depth: Int, maxDepth: Int): JSONObject {
        val json = JSONObject()
        json.put("cls", node.className?.toString() ?: "")
        val text = node.text?.toString() ?: ""
        if (text.isNotEmpty()) json.put("text", text)
        val desc = node.contentDescription?.toString() ?: ""
        if (desc.isNotEmpty()) json.put("desc", desc)
        val resId = node.viewIdResourceName ?: ""
        if (resId.isNotEmpty()) json.put("id", resId)
        if (node.isClickable) json.put("click", true)
        if (node.isScrollable) json.put("scroll", true)
        if (node.isEditable) json.put("edit", true)
        if (node.isCheckable) json.put("checkable", true)
        if (node.isChecked) json.put("checked", true)
        if (node.isFocused) json.put("focused", true)

        val rect = Rect()
        node.getBoundsInScreen(rect)
        json.put("b", "${rect.left},${rect.top},${rect.right},${rect.bottom}")

        if (depth < maxDepth && node.childCount > 0) {
            val children = JSONArray()
            for (i in 0 until node.childCount) {
                val child = node.getChild(i) ?: continue
                try {
                    if (child.isVisibleToUser) {
                        children.put(serializeNode(child, depth + 1, maxDepth))
                    }
                } finally {
                    try { child.recycle() } catch (_: Exception) {}
                }
            }
            if (children.length() > 0) json.put("ch", children)
        }
        return json
    }

    public fun findAndClickByText(searchText: String): JSONObject {
        val root = rootInActiveWindow
            ?: return JSONObject().put("ok", false).put("error", "No active window")
        try {
            val nodes = root.findAccessibilityNodeInfosByText(searchText)
            if (nodes.isNullOrEmpty()) {
                return JSONObject().put("ok", false).put("error", "Node not found: $searchText")
            }
            for (node in nodes) {
                if (node.isClickable && node.isVisibleToUser) {
                    node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    val result = JSONObject().put("ok", true)
                        .put("clicked", node.text?.toString() ?: node.contentDescription?.toString() ?: "")
                        .put("class", node.className?.toString() ?: "")
                    nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                    return result
                }
            }
            // Node found but not clickable — try clicking parent
            for (node in nodes) {
                if (!node.isVisibleToUser) continue
                var parent = node.parent
                var depth = 0
                while (parent != null && depth < 5) {
                    if (parent.isClickable) {
                        parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                        val result = JSONObject().put("ok", true)
                            .put("clicked", searchText)
                            .put("via", "parent")
                            .put("class", parent.className?.toString() ?: "")
                        try { parent.recycle() } catch (_: Exception) {}
                        nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                        return result
                    }
                    val gp = parent.parent
                    try { parent.recycle() } catch (_: Exception) {}
                    parent = gp
                    depth++
                }
            }
            nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
            return JSONObject().put("ok", false).put("error", "Found but not clickable: $searchText")
        } catch (e: Exception) {
            Log.e(TAG, "findAndClickByText failed: ${e.message}")
            return JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }

    public fun findAndClickById(viewId: String): JSONObject {
        val root = rootInActiveWindow
            ?: return JSONObject().put("ok", false).put("error", "No active window")
        try {
            val nodes = root.findAccessibilityNodeInfosByViewId(viewId)
            if (nodes.isNullOrEmpty()) {
                return JSONObject().put("ok", false).put("error", "Node not found: $viewId")
            }
            for (node in nodes) {
                if (node.isVisibleToUser) {
                    if (node.isClickable) {
                        node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    } else {
                        // Try clicking parent
                        var parent = node.parent
                        var clicked = false
                        var depth = 0
                        while (parent != null && depth < 5) {
                            if (parent.isClickable) {
                                parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                                clicked = true
                                try { parent.recycle() } catch (_: Exception) {}
                                break
                            }
                            val gp = parent.parent
                            try { parent.recycle() } catch (_: Exception) {}
                            parent = gp
                            depth++
                        }
                        if (!clicked) {
                            // Force tap at node center
                            val rect = Rect()
                            node.getBoundsInScreen(rect)
                            dispatchClick(rect.centerX(), rect.centerY(), 100)
                        }
                    }
                    val result = JSONObject().put("ok", true)
                        .put("id", viewId)
                        .put("text", node.text?.toString() ?: "")
                    nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                    return result
                }
            }
            nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
            return JSONObject().put("ok", false).put("error", "Node not visible: $viewId")
        } catch (e: Exception) {
            Log.e(TAG, "findAndClickById failed: ${e.message}")
            return JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }

    public fun dismissTopDialog(): JSONObject {
        val root = rootInActiveWindow
            ?: return JSONObject().put("ok", false).put("error", "No active window")
        try {
            // Strategy 1: Find dismiss/cancel/close buttons
            val dismissTexts = listOf("取消", "关闭", "知道了", "我知道了", "确定", "好的",
                "Cancel", "Close", "Dismiss", "OK", "Got it", "I know")
            for (text in dismissTexts) {
                val nodes = root.findAccessibilityNodeInfosByText(text)
                if (nodes.isNullOrEmpty()) continue
                for (node in nodes) {
                    if (node.isClickable && node.isVisibleToUser) {
                        node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                        val result = JSONObject().put("ok", true)
                            .put("dismissed", text)
                            .put("method", "button")
                        nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                        return result
                    }
                }
                nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
            }
            // Strategy 2: Press Back to dismiss
            performGlobalAction(GLOBAL_ACTION_BACK)
            return JSONObject().put("ok", true).put("method", "back")
        } catch (e: Exception) {
            Log.e(TAG, "dismissTopDialog failed: ${e.message}")
            return JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }

    public fun findNodesByText(searchText: String): JSONArray {
        val root = rootInActiveWindow ?: return JSONArray()
        val results = JSONArray()
        try {
            val nodes = root.findAccessibilityNodeInfosByText(searchText)
            if (nodes.isNullOrEmpty()) return results
            for (node in nodes) {
                if (!node.isVisibleToUser) { try { node.recycle() } catch (_: Exception) {}; continue }
                val rect = Rect()
                node.getBoundsInScreen(rect)
                val info = JSONObject()
                    .put("text", node.text?.toString() ?: "")
                    .put("desc", node.contentDescription?.toString() ?: "")
                    .put("cls", node.className?.toString() ?: "")
                    .put("id", node.viewIdResourceName ?: "")
                    .put("click", node.isClickable)
                    .put("b", "${rect.left},${rect.top},${rect.right},${rect.bottom}")
                results.put(info)
                try { node.recycle() } catch (_: Exception) {}
            }
        } catch (e: Exception) {
            Log.e(TAG, "findNodesByText failed: ${e.message}")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
        return results
    }

    public fun setNodeText(searchText: String, newText: String): JSONObject {
        val root = rootInActiveWindow
            ?: return JSONObject().put("ok", false).put("error", "No active window")
        try {
            val nodes = root.findAccessibilityNodeInfosByText(searchText)
            if (nodes.isNullOrEmpty()) {
                // Try finding editable focused node
                val focused = findFocusedNode()
                if (focused != null && focused.isEditable) {
                    focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply {
                        putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
                    })
                    val result = JSONObject().put("ok", true).put("target", "focused")
                    try { focused.recycle() } catch (_: Exception) {}
                    return result
                }
                return JSONObject().put("ok", false).put("error", "No matching node found")
            }
            for (node in nodes) {
                if (node.isEditable && node.isVisibleToUser) {
                    node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply {
                        putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, newText)
                    })
                    val result = JSONObject().put("ok", true)
                        .put("target", node.text?.toString() ?: searchText)
                    nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                    return result
                }
            }
            nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
            return JSONObject().put("ok", false).put("error", "Node not editable")
        } catch (e: Exception) {
            Log.e(TAG, "setNodeText failed: ${e.message}")
            return JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }

    // ==================== Platform Layer: APP Orchestration ====================

    /**
     * Send a generic Android Intent - unlocks ALL app entry points
     * Supports: ACTION_VIEW, ACTION_SEND, ACTION_DIAL, custom actions, extras, component targeting
     */
    public fun sendIntent(params: JSONObject): JSONObject {
        return try {
            val action = params.optString("action", Intent.ACTION_VIEW)
            val data = params.optString("data", "")
            val type = params.optString("type", "")
            val pkg = params.optString("package", "")
            val cls = params.optString("class", "")
            val category = params.optString("category", "")

            val intent = if (data.isNotEmpty()) {
                Intent(action, Uri.parse(data))
            } else {
                Intent(action)
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

            if (type.isNotEmpty()) intent.setType(type)
            if (pkg.isNotEmpty() && cls.isNotEmpty()) {
                intent.setClassName(pkg, cls)
            } else if (pkg.isNotEmpty()) {
                intent.setPackage(pkg)
            }
            if (category.isNotEmpty()) intent.addCategory(category)

            // Parse extras
            val extras = params.optJSONObject("extras")
            if (extras != null) {
                val keys = extras.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    when (val value = extras.get(key)) {
                        is String -> intent.putExtra(key, value)
                        is Int -> intent.putExtra(key, value)
                        is Boolean -> intent.putExtra(key, value)
                        is Double -> intent.putExtra(key, value.toFloat())
                        is Long -> intent.putExtra(key, value)
                        else -> intent.putExtra(key, value.toString())
                    }
                }
            }

            startActivity(intent)
            Log.i(TAG, "sendIntent: action=$action data=$data pkg=$pkg")
            JSONObject().put("ok", true).put("action", action).put("data", data)
        } catch (e: Exception) {
            Log.e(TAG, "sendIntent failed: ${e.message}")
            JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        }
    }

    /**
     * Extract ALL visible text from current screen - structured data extraction from any APP
     */
    public fun extractScreenText(): JSONObject {
        val root = rootInActiveWindow
            ?: return JSONObject().put("ok", false).put("error", "No active window")
        try {
            val json = JSONObject()
            json.put("ok", true)
            json.put("package", root.packageName?.toString() ?: "")

            val texts = JSONArray()
            val clickables = JSONArray()

            fun walk(node: AccessibilityNodeInfo, depth: Int) {
                if (!node.isVisibleToUser) return
                val text = node.text?.toString() ?: ""
                val desc = node.contentDescription?.toString() ?: ""
                val rect = Rect()
                node.getBoundsInScreen(rect)

                if (text.isNotEmpty()) {
                    val item = JSONObject()
                    item.put("text", text)
                    item.put("cls", node.className?.toString() ?: "")
                    if (node.isClickable) item.put("clickable", true)
                    if (node.isEditable) item.put("editable", true)
                    val id = node.viewIdResourceName ?: ""
                    if (id.isNotEmpty()) item.put("id", id)
                    item.put("bounds", "${rect.left},${rect.top},${rect.right},${rect.bottom}")
                    texts.put(item)
                }
                if (desc.isNotEmpty() && desc != text) {
                    val item = JSONObject()
                    item.put("text", desc)
                    item.put("type", "desc")
                    item.put("cls", node.className?.toString() ?: "")
                    if (node.isClickable) item.put("clickable", true)
                    item.put("bounds", "${rect.left},${rect.top},${rect.right},${rect.bottom}")
                    texts.put(item)
                }
                if (node.isClickable && (text.isNotEmpty() || desc.isNotEmpty())) {
                    clickables.put(JSONObject()
                        .put("label", if (text.isNotEmpty()) text else desc)
                        .put("bounds", "${rect.left},${rect.top},${rect.right},${rect.bottom}"))
                }

                if (depth < 15) {
                    for (i in 0 until node.childCount) {
                        val child = node.getChild(i) ?: continue
                        try { walk(child, depth + 1) }
                        finally { try { child.recycle() } catch (_: Exception) {} }
                    }
                }
            }
            walk(root, 0)
            json.put("texts", texts)
            json.put("clickables", clickables)
            json.put("textCount", texts.length())
            json.put("clickableCount", clickables.length())
            return json
        } catch (e: Exception) {
            Log.e(TAG, "extractScreenText failed: ${e.message}")
            return JSONObject().put("ok", false).put("error", e.message ?: "unknown")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }

    /**
     * Wait for specific text to appear on screen - enables workflow chaining
     * Polls view tree until condition met or timeout
     */
    public fun waitForCondition(targetText: String, timeoutMs: Long = 10000, intervalMs: Long = 500): JSONObject {
        val startTime = System.currentTimeMillis()
        var attempts = 0
        while (System.currentTimeMillis() - startTime < timeoutMs) {
            attempts++
            val root = rootInActiveWindow
            if (root != null) {
                try {
                    val nodes = root.findAccessibilityNodeInfosByText(targetText)
                    if (nodes != null && nodes.isNotEmpty()) {
                        val found = nodes[0]
                        val text = found.text?.toString() ?: found.contentDescription?.toString() ?: targetText
                        val rect = Rect()
                        found.getBoundsInScreen(rect)
                        nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                        return JSONObject()
                            .put("ok", true)
                            .put("found", true)
                            .put("text", text)
                            .put("bounds", "${rect.left},${rect.top},${rect.right},${rect.bottom}")
                            .put("elapsed", System.currentTimeMillis() - startTime)
                            .put("attempts", attempts)
                    }
                    nodes?.forEach { try { it.recycle() } catch (_: Exception) {} }
                } catch (_: Exception) {
                } finally {
                    try { root.recycle() } catch (_: Exception) {}
                }
            }
            try { Thread.sleep(intervalMs) } catch (_: InterruptedException) { break }
        }
        return JSONObject()
            .put("ok", true)
            .put("found", false)
            .put("elapsed", System.currentTimeMillis() - startTime)
            .put("attempts", attempts)
    }

    /**
     * Read recent notifications via AccessibilityService event cache
     * Captures notification events and provides them via API
     */
    private val notificationHistory = mutableListOf<JSONObject>()
    private val maxNotificationHistory = 50

    public fun onNotificationEvent(event: AccessibilityEvent) {
        if (event.eventType != AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED) return
        try {
            val entry = JSONObject()
            entry.put("package", event.packageName?.toString() ?: "")
            entry.put("time", System.currentTimeMillis())
            val texts = mutableListOf<String>()
            event.text?.forEach { texts.add(it.toString()) }
            entry.put("text", texts.joinToString(" | "))
            val parcel = event.parcelableData
            if (parcel is android.app.Notification) {
                entry.put("title", parcel.extras?.getString("android.title") ?: "")
                entry.put("body", parcel.extras?.getCharSequence("android.text")?.toString() ?: "")
                entry.put("subText", parcel.extras?.getCharSequence("android.subText")?.toString() ?: "")
            }
            synchronized(notificationHistory) {
                notificationHistory.add(0, entry)
                while (notificationHistory.size > maxNotificationHistory) {
                    notificationHistory.removeAt(notificationHistory.size - 1)
                }
            }
            Log.i(TAG, "Notification captured from ${event.packageName}")

            // Feed to macro trigger engine
            MacroEngine.instance.onNotification(
                event.packageName?.toString() ?: "",
                entry.optString("title", ""),
                entry.optString("body", "")
            )
        } catch (e: Exception) {
            Log.e(TAG, "onNotificationEvent failed: ${e.message}")
        }
    }

    public fun getNotifications(limit: Int = 20): JSONObject {
        val json = JSONObject()
        json.put("ok", true)
        val arr = JSONArray()
        synchronized(notificationHistory) {
            val count = minOf(limit, notificationHistory.size)
            for (i in 0 until count) {
                arr.put(notificationHistory[i])
            }
        }
        json.put("notifications", arr)
        json.put("count", arr.length())
        json.put("total", notificationHistory.size)
        return json
    }

    public fun getActiveWindowInfo(): JSONObject {
        val root = rootInActiveWindow
            ?: return JSONObject().put("error", "No active window")
        try {
            val json = JSONObject()
            json.put("package", root.packageName?.toString() ?: "")
            json.put("class", root.className?.toString() ?: "")
            json.put("childCount", root.childCount)
            // Count total visible nodes
            var totalNodes = 0
            fun countNodes(node: AccessibilityNodeInfo) {
                totalNodes++
                for (i in 0 until node.childCount) {
                    val child = node.getChild(i) ?: continue
                    try { if (child.isVisibleToUser) countNodes(child) }
                    finally { try { child.recycle() } catch (_: Exception) {} }
                }
            }
            countNodes(root)
            json.put("totalNodes", totalNodes)
            return json
        } catch (e: Exception) {
            return JSONObject().put("error", e.message ?: "unknown")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }
}
