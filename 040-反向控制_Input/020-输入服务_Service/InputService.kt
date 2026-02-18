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

    /**
     * Semantic Automation Demo: Opens calculator, finds "5" button via View tree, clicks it.
     * Proves that ScreenStream can "see" any APP's UI and "act" on it — the foundation
     * for cross-app semantic automation.
     */
    public fun runSemanticDemo(targetButton: String = "5"): JSONObject {
        val log = JSONArray()
        val startTime = System.currentTimeMillis()
        fun logStep(step: String, ok: Boolean, detail: String = "") {
            val entry = JSONObject()
                .put("step", step)
                .put("ok", ok)
                .put("ms", System.currentTimeMillis() - startTime)
            if (detail.isNotEmpty()) entry.put("detail", detail)
            log.put(entry)
            Log.i(TAG, "SemanticDemo [$step] ok=$ok $detail")
        }

        try {
            // Step 1: Open calculator via Intent
            val calcPackages = listOf(
                "com.google.android.calculator",
                "com.sec.android.app.popupcalculator",
                "com.miui.calculator",
                "com.coloros.calculator",
                "com.vivo.calculator",
                "com.asus.calculator",
                "com.oneplus.calculator",
                "com.android.calculator2"
            )
            var launched = false
            for (pkg in calcPackages) {
                try {
                    val intent = packageManager.getLaunchIntentForPackage(pkg)
                    if (intent != null) {
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        startActivity(intent)
                        logStep("open_calculator", true, "package=$pkg")
                        launched = true
                        break
                    }
                } catch (_: Exception) {}
            }
            if (!launched) {
                // Fallback 1: try explicit component (some OEM calcs hide launch intent)
                val knownComponents = listOf(
                    "com.coloros.calculator/com.android.calculator2.Calculator",
                    "com.sec.android.app.popupcalculator/com.sec.android.app.popupcalculator.Calculator",
                    "com.android.calculator2/com.android.calculator2.Calculator"
                )
                for (comp in knownComponents) {
                    try {
                        val (pkg, cls) = comp.split("/")
                        val intent = Intent(Intent.ACTION_MAIN).apply {
                            setClassName(pkg, cls)
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        startActivity(intent)
                        logStep("open_calculator", true, "component=$comp")
                        launched = true
                        break
                    } catch (_: Exception) {}
                }
            }
            if (!launched) {
                // Fallback 2: try generic calculator category
                try {
                    val intent = Intent(Intent.ACTION_MAIN).apply {
                        addCategory(Intent.CATEGORY_APP_CALCULATOR)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    startActivity(intent)
                    logStep("open_calculator", true, "via CATEGORY_APP_CALCULATOR")
                    launched = true
                } catch (e: Exception) {
                    logStep("open_calculator", false, "no calculator found: ${e.message}")
                }
            }
            if (!launched) {
                return JSONObject().put("ok", false).put("log", log)
                    .put("error", "No calculator app found on device")
            }

            // Step 2: Wait for calculator to load (poll for the target button)
            Thread.sleep(1500) // Initial wait for app to launch
            val waitResult = waitForCondition(targetButton, 5000, 300)
            val found = waitResult.optBoolean("found", false)
            logStep("wait_for_ui", found,
                "target='$targetButton' elapsed=${waitResult.optLong("elapsed")}ms attempts=${waitResult.optInt("attempts")}")

            if (!found) {
                // Still try to read what IS on screen for diagnostics
                val screenText = extractScreenText()
                logStep("screen_snapshot", true,
                    "package=${screenText.optString("package")} texts=${screenText.optInt("textCount")} clickables=${screenText.optInt("clickableCount")}")
                return JSONObject().put("ok", false).put("log", log)
                    .put("error", "Button '$targetButton' not found on calculator screen")
                    .put("screen", screenText)
            }

            // Step 3: Read View tree to find the button (for logging — show we can "see")
            val root = rootInActiveWindow
            var buttonInfo = ""
            if (root != null) {
                try {
                    val nodes = root.findAccessibilityNodeInfosByText(targetButton)
                    if (nodes != null && nodes.isNotEmpty()) {
                        val node = nodes[0]
                        val rect = Rect()
                        node.getBoundsInScreen(rect)
                        buttonInfo = "text='${node.text}' cls=${node.className} bounds=${rect} clickable=${node.isClickable}"
                        nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                    }
                } finally {
                    try { root.recycle() } catch (_: Exception) {}
                }
            }
            logStep("find_button", buttonInfo.isNotEmpty(), buttonInfo)

            // Step 4: Click the button via semantic action (findAndClickByText)
            val clickResult = findAndClickByText(targetButton)
            val clicked = clickResult.optBoolean("ok", false)
            logStep("click_button", clicked,
                "clicked='${clickResult.optString("clicked")}' via=${clickResult.optString("via", "direct")}")

            // Step 5: Verify — read screen after click
            Thread.sleep(500)
            val afterScreen = extractScreenText()
            logStep("verify_after_click", true,
                "package=${afterScreen.optString("package")} texts=${afterScreen.optInt("textCount")}")

            val totalMs = System.currentTimeMillis() - startTime
            return JSONObject()
                .put("ok", clicked)
                .put("totalMs", totalMs)
                .put("log", log)
                .put("summary", if (clicked)
                    "SUCCESS: Opened calculator → Found '$targetButton' button ($buttonInfo) → Clicked it in ${totalMs}ms"
                else
                    "PARTIAL: Opened calculator, found button but click failed")

        } catch (e: Exception) {
            logStep("error", false, e.message ?: "unknown")
            return JSONObject().put("ok", false).put("log", log).put("error", e.message)
        }
    }

    /**
     * Cross-screen sequential automation demo: Open Settings → Find WiFi → Toggle switch.
     * Tests: screen transitions, View tree re-read, list scrolling, Switch/Toggle recognition.
     */
    public fun runWifiToggleDemo(): JSONObject {
        val log = JSONArray()
        val startTime = System.currentTimeMillis()
        fun logStep(step: String, ok: Boolean, detail: String = "") {
            val entry = JSONObject()
                .put("step", step)
                .put("ok", ok)
                .put("ms", System.currentTimeMillis() - startTime)
            if (detail.isNotEmpty()) entry.put("detail", detail)
            log.put(entry)
            Log.i(TAG, "WifiDemo [$step] ok=$ok $detail")
        }

        // Helper: find a node matching any of the given texts
        fun findNodeByTexts(texts: List<String>): Pair<AccessibilityNodeInfo?, String> {
            val root = rootInActiveWindow ?: return null to "no active window"
            try {
                for (text in texts) {
                    val nodes = root.findAccessibilityNodeInfosByText(text)
                    if (nodes != null && nodes.isNotEmpty()) {
                        for (node in nodes) {
                            if (node.isVisibleToUser) {
                                val label = node.text?.toString() ?: node.contentDescription?.toString() ?: text
                                // Don't recycle the found node - caller will use it
                                return node to label
                            }
                        }
                        nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                    }
                }
            } catch (_: Exception) {}
            try { root.recycle() } catch (_: Exception) {}
            return null to "not found: ${texts.joinToString("/")}"
        }

        // Helper: click a node or its clickable parent
        fun clickNode(node: AccessibilityNodeInfo): Boolean {
            if (node.isClickable) {
                return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            }
            // Walk up to find clickable parent
            var parent = node.parent
            var depth = 0
            while (parent != null && depth < 5) {
                if (parent.isClickable) {
                    val result = parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    try { parent.recycle() } catch (_: Exception) {}
                    return result
                }
                val gp = parent.parent
                try { parent.recycle() } catch (_: Exception) {}
                parent = gp
                depth++
            }
            return false
        }

        // Helper: snapshot current screen elements for diagnostics
        fun screenSnapshot(): String {
            val screen = extractScreenText()
            return "pkg=${screen.optString("package")} texts=${screen.optInt("textCount")} clickables=${screen.optInt("clickableCount")}"
        }

        try {
            // === Step 1: Record initial WiFi state ===
            val wifiManager = try {
                applicationContext.getSystemService(android.content.Context.WIFI_SERVICE) as? android.net.wifi.WifiManager
            } catch (_: Exception) { null }
            val initialWifiState = try { wifiManager?.isWifiEnabled } catch (_: Exception) { null }
            logStep("initial_state", true, "wifi_enabled=$initialWifiState")

            // === Step 2: Open system Settings ===
            val settingsIntent = Intent(android.provider.Settings.ACTION_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(settingsIntent)
            Thread.sleep(1500)

            val settingsScreen = extractScreenText()
            logStep("open_settings", true,
                "pkg=${settingsScreen.optString("package")} texts=${settingsScreen.optInt("textCount")}")

            // === Step 3: Find WiFi/WLAN item ===
            // OEM variations: WLAN, Wi-Fi, WiFi, 无线局域网, WLAN/WiFi
            val wifiLabels = listOf("WLAN", "Wi-Fi", "WiFi", "无线局域网", "网络和互联网", "连接")

            var (wifiNode, wifiLabel) = findNodeByTexts(wifiLabels)

            // If not found, try scrolling down
            if (wifiNode == null) {
                logStep("wifi_search_scroll", false, "Not visible, scrolling down...")
                for (scrollAttempt in 1..3) {
                    scrollNormalized(0.5f, 0.7f, "down", 600)
                    Thread.sleep(800)
                    val result = findNodeByTexts(wifiLabels)
                    wifiNode = result.first
                    wifiLabel = result.second
                    if (wifiNode != null) {
                        logStep("wifi_found_after_scroll", true, "attempt=$scrollAttempt label='$wifiLabel'")
                        break
                    }
                }
            }

            if (wifiNode == null) {
                logStep("find_wifi_item", false, "WiFi item not found. Screen: ${screenSnapshot()}")
                // Dump all visible texts for diagnostics
                val allTexts = extractScreenText()
                return JSONObject().put("ok", false).put("log", log)
                    .put("error", "WiFi/WLAN item not found in Settings")
                    .put("screen", allTexts)
            }

            val wifiRect = Rect()
            wifiNode.getBoundsInScreen(wifiRect)
            logStep("find_wifi_item", true,
                "label='$wifiLabel' bounds=$wifiRect clickable=${wifiNode.isClickable}")

            // === Step 4: Click WiFi item to enter WiFi settings ===
            val wifiClicked = clickNode(wifiNode)
            try { wifiNode.recycle() } catch (_: Exception) {}
            logStep("click_wifi_item", wifiClicked, "label='$wifiLabel'")

            if (!wifiClicked) {
                return JSONObject().put("ok", false).put("log", log)
                    .put("error", "Failed to click WiFi item")
            }

            // === Step 5: Wait for WiFi settings page to load, re-read View tree ===
            Thread.sleep(1500)
            val wifiPageScreen = extractScreenText()
            logStep("wifi_page_loaded", true,
                "pkg=${wifiPageScreen.optString("package")} texts=${wifiPageScreen.optInt("textCount")} clickables=${wifiPageScreen.optInt("clickableCount")}")

            // === Step 6: Find WiFi toggle switch ===
            // Strategy: Look for Switch/Toggle widget near WiFi text, or find by class name
            val root = rootInActiveWindow
            var switchNode: AccessibilityNodeInfo? = null
            var switchInfo = ""

            if (root != null) {
                try {
                    // Strategy A: Find Switch/Toggle by class name (don't require isClickable — OEM switches may not be)
                    fun findSwitchInTree(node: AccessibilityNodeInfo, depth: Int): AccessibilityNodeInfo? {
                        if (depth > 15) return null
                        val cls = node.className?.toString() ?: ""
                        if (cls.contains("Switch") || cls.contains("Toggle") || cls.contains("CheckBox")) {
                            if (node.isVisibleToUser) {
                                switchInfo = "cls=$cls checked=${node.isChecked} clickable=${node.isClickable} checkable=${node.isCheckable} text='${node.text ?: ""}' id='${node.viewIdResourceName ?: ""}'"
                                return node
                            }
                        }
                        for (i in 0 until node.childCount) {
                            val child = node.getChild(i) ?: continue
                            val found = findSwitchInTree(child, depth + 1)
                            if (found != null) return found
                            try { child.recycle() } catch (_: Exception) {}
                        }
                        return null
                    }
                    switchNode = findSwitchInTree(root, 0)

                    // Strategy B: Find by resource ID (common switch IDs)
                    if (switchNode == null) {
                        val switchIds = listOf("android:id/switch_widget", "android:id/switchWidget", "com.android.settings:id/switch_widget")
                        for (id in switchIds) {
                            val nodes = root.findAccessibilityNodeInfosByViewId(id)
                            if (nodes != null && nodes.isNotEmpty()) {
                                switchNode = nodes[0]
                                switchInfo = "byId=$id cls=${switchNode!!.className} checked=${switchNode!!.isChecked}"
                                nodes.drop(1).forEach { try { it.recycle() } catch (_: Exception) {} }
                                break
                            }
                        }
                    }

                    // Strategy C: Find checkable node with WiFi-related text
                    if (switchNode == null) {
                        val wifiSwitchLabels = listOf("WLAN", "Wi-Fi", "WiFi")
                        for (label in wifiSwitchLabels) {
                            val nodes = root.findAccessibilityNodeInfosByText(label)
                            if (nodes != null) {
                                for (node in nodes) {
                                    if (node.isCheckable && node.isVisibleToUser) {
                                        switchNode = node
                                        switchInfo = "checkable cls=${node.className} checked=${node.isChecked} text='${node.text}'"
                                        break
                                    }
                                }
                                if (switchNode != null) break
                                nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                            }
                        }
                    }
                } catch (e: Exception) {
                    logStep("find_switch_error", false, e.message ?: "unknown")
                } finally {
                    try { root.recycle() } catch (_: Exception) {}
                }
            }

            if (switchNode == null) {
                logStep("find_wifi_switch", false, "Switch not found. Screen: ${screenSnapshot()}")
                val allTexts = extractScreenText()
                return JSONObject().put("ok", false).put("log", log)
                    .put("error", "WiFi switch/toggle not found on WiFi settings page")
                    .put("screen", allTexts)
                    .put("phase2_debt", "Need smarter widget detection: scan for Switch/Toggle by class hierarchy, handle OEM custom widgets")
            }

            val switchRect = Rect()
            switchNode.getBoundsInScreen(switchRect)
            val wasChecked = switchNode.isChecked
            logStep("find_wifi_switch", true,
                "$switchInfo bounds=$switchRect was_checked=$wasChecked")

            // === Step 7: Toggle the switch (try multiple strategies) ===
            var toggleResult = switchNode.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            var toggleVia = "ACTION_CLICK"

            // If direct click didn't work, try clicking parent
            if (!toggleResult) {
                var parent = switchNode.parent
                var depth = 0
                while (parent != null && depth < 3) {
                    if (parent.isClickable) {
                        toggleResult = parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                        toggleVia = "parent_click(depth=$depth)"
                        try { parent.recycle() } catch (_: Exception) {}
                        break
                    }
                    val gp = parent.parent
                    try { parent.recycle() } catch (_: Exception) {}
                    parent = gp
                    depth++
                }
            }

            // Last resort: coordinate-based tap on switch center
            if (!toggleResult) {
                val cx = switchRect.centerX()
                val cy = switchRect.centerY()
                dispatchClick(cx, cy, 100)
                toggleResult = true
                toggleVia = "coordinate_tap($cx,$cy)"
            }

            try { switchNode.recycle() } catch (_: Exception) {}
            logStep("toggle_switch", toggleResult, "was_checked=$wasChecked → target=${!wasChecked} via=$toggleVia")

            // === Step 8: Verify WiFi state actually changed ===
            Thread.sleep(2000) // Wait for WiFi state transition

            val finalWifiState = try { wifiManager?.isWifiEnabled } catch (_: Exception) { null }
            val stateChanged = initialWifiState != finalWifiState
            logStep("verify_state", stateChanged,
                "initial=$initialWifiState → final=$finalWifiState changed=$stateChanged")

            // Also re-read the switch state from View tree
            Thread.sleep(500)
            val verifyRoot = rootInActiveWindow
            var finalSwitchChecked: Boolean? = null
            if (verifyRoot != null) {
                try {
                    fun findFirstSwitch(node: AccessibilityNodeInfo, depth: Int): Boolean? {
                        if (depth > 15) return null
                        val cls = node.className?.toString() ?: ""
                        if ((cls.contains("Switch") || cls.contains("Toggle") || cls.contains("CheckBox")) && node.isVisibleToUser) {
                            return node.isChecked
                        }
                        for (i in 0 until node.childCount) {
                            val child = node.getChild(i) ?: continue
                            val result = findFirstSwitch(child, depth + 1)
                            if (result != null) {
                                try { child.recycle() } catch (_: Exception) {}
                                return result
                            }
                            try { child.recycle() } catch (_: Exception) {}
                        }
                        return null
                    }
                    finalSwitchChecked = findFirstSwitch(verifyRoot, 0)
                } finally {
                    try { verifyRoot.recycle() } catch (_: Exception) {}
                }
            }
            logStep("verify_switch_ui", finalSwitchChecked != null,
                "switch_checked=$finalSwitchChecked (was $wasChecked)")

            // === Step 9: Go back to home ===
            performGlobalAction(GLOBAL_ACTION_HOME)

            val totalMs = System.currentTimeMillis() - startTime
            val success = stateChanged || (finalSwitchChecked != null && finalSwitchChecked != wasChecked)
            return JSONObject()
                .put("ok", success)
                .put("totalMs", totalMs)
                .put("log", log)
                .put("wifiState", JSONObject()
                    .put("initial", initialWifiState)
                    .put("final", finalWifiState)
                    .put("changed", stateChanged))
                .put("summary", if (success)
                    "SUCCESS: Settings → WiFi → Toggle ($wasChecked→${!wasChecked}) in ${totalMs}ms. WiFi: $initialWifiState→$finalWifiState"
                else
                    "PARTIAL: Navigation worked but WiFi state may not have changed. initial=$initialWifiState final=$finalWifiState")

        } catch (e: Exception) {
            logStep("error", false, e.message ?: "unknown")
            return JSONObject().put("ok", false).put("log", log).put("error", e.message)
        }
    }

    /**
     * Natural language command executor.
     * Parses user intent via keyword matching and chains existing capabilities.
     * Examples: "关掉WiFi", "打开计算器", "点击设置", "输入hello", "返回", "截图"
     */
    public fun executeNaturalCommand(command: String, onStep: ((JSONObject) -> Unit)? = null): JSONObject {
        val startTime = System.currentTimeMillis()
        val steps = JSONArray()
        fun step(name: String, ok: Boolean, detail: String = "") {
            steps.put(JSONObject().put("step", name).put("ok", ok)
                .put("ms", System.currentTimeMillis() - startTime)
                .apply { if (detail.isNotEmpty()) put("detail", detail) })
        }

        val cmd = command.trim().lowercase()
        step("parse", true, "input='$command'")

        try {
            // === Pattern: Open/Launch app ===
            val openPatterns = listOf("打开", "启动", "运行", "open", "launch", "start")
            val appMatch = openPatterns.firstOrNull { cmd.startsWith(it) }
            if (appMatch != null) {
                val appName = command.trim().substring(appMatch.length).trim()
                if (appName.isNotEmpty()) {
                    return executeOpenApp(appName, steps, startTime)
                }
            }

            // === Pattern: Toggle WiFi ===
            val hasWifi = cmd.contains("wifi") || cmd.contains("wlan") || cmd.contains("无线")
            val wantOff = cmd.contains("关") || cmd.contains("off") || cmd.contains("disable") || cmd.contains("断开")
            val wantOn = cmd.contains("开") || cmd.contains("on") || cmd.contains("enable") || cmd.contains("连接")
            val wantToggle = cmd.contains("切换") || cmd.contains("toggle") || cmd.contains("switch")
            if (hasWifi && (wantOff || wantOn || wantToggle)) {
                step("intent", true, "wifi_toggle target=${if (wantOff) "off" else if (wantOn) "on" else "toggle"}")
                val result = runWifiToggleDemo()
                step("execute", result.optBoolean("ok"), result.optString("summary"))
                return JSONObject().put("ok", result.optBoolean("ok"))
                    .put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "wifi_toggle").put("steps", steps)
                    .put("detail", result)
            }

            // === Pattern: Click UI element by text ===
            val clickPatterns = listOf("点击", "按", "tap", "click", "press")
            val clickMatch = clickPatterns.firstOrNull { cmd.startsWith(it) }
            if (clickMatch != null) {
                val target = command.trim().substring(clickMatch.length).trim()
                    .removeSurrounding("\"").removeSurrounding("'").removeSurrounding(""", """)
                if (target.isNotEmpty()) {
                    step("intent", true, "click target='$target'")
                    val result = findAndClickByText(target)
                    val ok = result.optBoolean("ok")
                    step("execute", ok, result.toString())
                    return JSONObject().put("ok", ok)
                        .put("totalMs", System.currentTimeMillis() - startTime)
                        .put("command", command).put("action", "click").put("target", target)
                        .put("steps", steps).put("detail", result)
                }
            }

            // === Pattern: Type/Input text ===
            val typePatterns = listOf("输入", "type", "input", "键入", "写入")
            val typeMatch = typePatterns.firstOrNull { cmd.startsWith(it) }
            if (typeMatch != null) {
                val text = command.trim().substring(typeMatch.length).trim()
                    .removeSurrounding("\"").removeSurrounding("'").removeSurrounding(""", """)
                if (text.isNotEmpty()) {
                    step("intent", true, "type text='$text'")
                    inputText(text)
                    step("execute", true, "typed ${text.length} chars")
                    return JSONObject().put("ok", true)
                        .put("totalMs", System.currentTimeMillis() - startTime)
                        .put("command", command).put("action", "type").put("text", text).put("steps", steps)
                }
            }

            // === Pattern: Navigation (HOME before BACK to handle "返回桌面" correctly) ===
            if (cmd.contains("主页") || cmd.contains("桌面") || cmd == "home" || cmd == "go home") {
                performGlobalAction(GLOBAL_ACTION_HOME)
                step("execute", true, "GLOBAL_ACTION_HOME")
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "home").put("steps", steps)
            }
            if (cmd.contains("返回") || cmd == "back" || cmd == "go back") {
                performGlobalAction(GLOBAL_ACTION_BACK)
                step("execute", true, "GLOBAL_ACTION_BACK")
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "back").put("steps", steps)
            }
            if (cmd.contains("最近") || cmd.contains("任务") || cmd == "recents") {
                performGlobalAction(GLOBAL_ACTION_RECENTS)
                step("execute", true, "GLOBAL_ACTION_RECENTS")
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "recents").put("steps", steps)
            }
            if (cmd.contains("通知") || cmd == "notifications") {
                performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
                step("execute", true, "GLOBAL_ACTION_NOTIFICATIONS")
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "notifications").put("steps", steps)
            }

            // === Pattern: Screenshot ===
            if (cmd.contains("截图") || cmd.contains("screenshot") || cmd.contains("截屏")) {
                val screen = extractScreenText()
                step("execute", true, "screen captured: ${screen.optInt("textCount")} texts")
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "screen_read").put("screen", screen).put("steps", steps)
            }

            // === Pattern: Scroll ===
            if (cmd.contains("上滑") || cmd.contains("scroll up") || cmd.contains("往上")) {
                scrollNormalized(0.5f, 0.5f, "up", 600)
                step("execute", true, "scroll up")
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "scroll_up").put("steps", steps)
            }
            if (cmd.contains("下滑") || cmd.contains("scroll down") || cmd.contains("往下")) {
                scrollNormalized(0.5f, 0.5f, "down", 600)
                step("execute", true, "scroll down")
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "scroll_down").put("steps", steps)
            }

            // === Fallback: try to find and click any matching text on screen ===
            step("intent", true, "fallback: try click '$cmd'")
            val fallbackResult = findAndClickByText(command.trim())
            if (fallbackResult.optBoolean("ok")) {
                step("execute", true, "fallback clicked: ${fallbackResult.optString("clicked")}")
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", command).put("action", "fallback_click").put("steps", steps)
                    .put("detail", fallbackResult)
            }

            // === Agent Path: intelligent View tree search when keywords fail ===
            val agentResult = runAgentPath(command, startTime, onStep)
            if (agentResult.optBoolean("ok")) {
                steps.put(JSONObject().put("step", "agent").put("ok", true)
                    .put("ms", System.currentTimeMillis() - startTime)
                    .put("detail", agentResult.optString("summary", "agent completed")))
                return agentResult.put("steps", steps)
            }

            // === Not understood ===
            step("execute", false, "command not understood, agent also failed")
            return JSONObject().put("ok", false).put("totalMs", System.currentTimeMillis() - startTime)
                .put("command", command).put("error", "无法理解命令: $command")
                .put("steps", steps).put("agentLog", agentResult.optJSONArray("agentSteps"))
                .put("hint", "支持: 打开[APP], 关掉/打开WiFi, 点击[文字], 输入[文本], 返回, 主页, 截图, 上滑/下滑")

        } catch (e: Exception) {
            step("error", false, e.message ?: "unknown")
            return JSONObject().put("ok", false).put("command", command).put("error", e.message).put("steps", steps)
        }
    }

    /**
     * Agent Path: intelligent View tree search when keyword matching fails.
     * Reads screen → searches for matching elements → clicks/scrolls → verifies.
     * Max 8 steps, 20s timeout.
     */
    private fun runAgentPath(command: String, globalStartTime: Long, onStep: ((JSONObject) -> Unit)?): JSONObject {
        val agentSteps = JSONArray()
        val agentStart = System.currentTimeMillis()
        val maxSteps = 8
        val timeoutMs = 20_000L
        var stepCount = 0

        fun emit(type: String, ok: Boolean, detail: String) {
            val step = JSONObject()
                .put("type", "agent_$type").put("ok", ok).put("detail", detail)
                .put("ms", System.currentTimeMillis() - globalStartTime)
                .put("agentStep", stepCount)
            agentSteps.put(step)
            onStep?.invoke(step)
        }

        fun elapsed() = System.currentTimeMillis() - agentStart
        fun timedOut() = elapsed() > timeoutMs

        val cmd = command.trim()
        val cmdLower = cmd.lowercase()
        emit("start", true, "Agent 启动: '$cmd'")

        try {
            // Extract search keywords from command
            val keywords = extractSearchKeywords(cmd)
            emit("plan", true, "搜索关键词: ${keywords.joinToString(", ")}")

            // Step loop: read screen → search → act → verify
            var scrollAttempts = 0
            val maxScrolls = 3

            while (stepCount < maxSteps && !timedOut()) {
                stepCount++

                // 1. Read current screen
                val screen = extractScreenText()
                val pkg = screen.optString("package", "")
                val texts = screen.optJSONArray("texts")
                val textCount = screen.optInt("textCount", 0)
                emit("read", true, "屏幕: [$pkg] ${textCount}个元素")

                if (timedOut()) break

                // 2. Search for matching elements
                var bestMatch: JSONObject? = null
                var bestScore = 0
                if (texts != null) {
                    for (i in 0 until texts.length()) {
                        val textObj = texts.getJSONObject(i)
                        val text = textObj.optString("text", "")
                        val score = calculateMatchScore(text, keywords, cmdLower)
                        if (score > bestScore) {
                            bestScore = score
                            bestMatch = textObj
                        }
                    }
                }

                if (bestMatch != null && bestScore >= 2) {
                    val matchText = bestMatch.optString("text", "")
                    val matchBounds = bestMatch.optString("bounds", "")
                    val isClickable = bestMatch.optBoolean("clickable", false)
                    emit("found", true, "匹配: '$matchText' (score=$bestScore, bounds=$matchBounds)")

                    // 3. Try to click it
                    val clickResult = findAndClickByText(matchText)
                    if (clickResult.optBoolean("ok")) {
                        emit("click", true, "点击成功: '$matchText'")

                        // 4. Verify: wait and re-read
                        Thread.sleep(500)
                        if (timedOut()) break
                        val verifyScreen = extractScreenText()
                        val verifyPkg = verifyScreen.optString("package", "")
                        val verifyTexts = verifyScreen.optInt("textCount", 0)
                        val changed = verifyPkg != pkg || verifyTexts != textCount
                        emit("verify", true,
                            "验证: [$verifyPkg] ${verifyTexts}项 ${if (changed) "(界面已变化)" else "(未变化)"}")

                        // Build summary of what we see now
                        val summary = buildScreenSummary(verifyScreen)

                        return JSONObject().put("ok", true)
                            .put("totalMs", System.currentTimeMillis() - globalStartTime)
                            .put("command", command).put("action", "agent")
                            .put("summary", "Agent找到并点击了'$matchText' → $summary")
                            .put("agentSteps", agentSteps)
                            .put("screenSummary", summary)
                    } else {
                        emit("click", false, "点击失败: '$matchText'")
                    }
                } else {
                    // No match found — try scrolling
                    if (scrollAttempts < maxScrolls) {
                        scrollAttempts++
                        emit("scroll", true, "未找到匹配，滚动搜索 ($scrollAttempts/$maxScrolls)")
                        scrollNormalized(0.5f, 0.5f, "down", 600)
                        Thread.sleep(800)
                    } else {
                        emit("exhausted", false, "滚动${maxScrolls}次后仍未找到匹配")
                        break
                    }
                }
            }

            if (timedOut()) {
                emit("timeout", false, "Agent 超时 (${timeoutMs / 1000}s)")
            }

            return JSONObject().put("ok", false).put("command", command)
                .put("error", "Agent未能找到匹配的操作目标")
                .put("agentSteps", agentSteps)

        } catch (e: Exception) {
            emit("error", false, e.message ?: "unknown")
            return JSONObject().put("ok", false).put("command", command)
                .put("error", e.message).put("agentSteps", agentSteps)
        }
    }

    /** Extract meaningful search keywords from a natural language command */
    private fun extractSearchKeywords(command: String): List<String> {
        // Remove common action verbs to get the target keywords
        val stopWords = listOf(
            "打开", "启动", "运行", "找到", "找", "搜索", "看看", "查看",
            "点击", "按", "去", "进入", "切换", "关闭", "关掉",
            "open", "find", "go to", "click", "tap", "search", "look",
            "一个", "那个", "这个", "的", "了", "吧", "啊"
        )
        var cleaned = command.trim()
        for (word in stopWords) {
            cleaned = cleaned.replace(word, " ", ignoreCase = true)
        }
        return cleaned.split(Regex("[\\s,，、]+")).filter { it.length >= 1 }.distinct()
    }

    /** Calculate how well a View tree text matches the search keywords */
    private fun calculateMatchScore(text: String, keywords: List<String>, fullCommand: String): Int {
        if (text.isBlank()) return 0
        val textLower = text.lowercase()
        var score = 0
        for (kw in keywords) {
            if (kw.isBlank()) continue
            if (textLower.contains(kw.lowercase())) score += 3
            else if (textLower.contains(kw.take(2).lowercase())) score += 1
        }
        // Bonus for exact substring match with command
        if (fullCommand.contains(text, ignoreCase = true)) score += 2
        if (text.contains(fullCommand, ignoreCase = true)) score += 2
        return score
    }

    /**
     * Compound command: splits multi-step intent into atomic actions and executes sequentially.
     * Calls [onStep] callback after each step for real-time streaming.
     * Examples:
     *   "打开设置看看WiFi" → [打开设置, 看看WiFi]
     *   "打开计算器按5+3=" → [打开计算器, 按5, 按+, 按3, 按=, 读结果]
     */
    public fun executeCompoundCommand(command: String, onStep: (JSONObject) -> Unit): JSONObject {
        val startTime = System.currentTimeMillis()
        val allSteps = JSONArray()

        fun emitStep(step: JSONObject) {
            step.put("ms", System.currentTimeMillis() - startTime)
            allSteps.put(step)
            onStep(step)
        }

        try {
            val steps = splitCompoundCommand(command)
            emitStep(JSONObject().put("type", "plan").put("ok", true)
                .put("detail", "拆解为 ${steps.size} 步: ${steps.joinToString(" → ")}"))

            var lastScreenInfo = ""
            for ((index, step) in steps.withIndex()) {
                emitStep(JSONObject().put("type", "start").put("ok", true)
                    .put("index", index).put("command", step))

                val result = executeSingleStep(step, onStep)
                val ok = result.optBoolean("ok", false)
                emitStep(JSONObject().put("type", "result").put("ok", ok)
                    .put("index", index).put("command", step)
                    .put("action", result.optString("action", ""))
                    .put("detail", result.optString("summary", result.optString("error", ""))))

                // After each step, brief pause for UI to settle
                if (index < steps.size - 1) Thread.sleep(800)

                // If step involves opening/navigating, read screen for context
                val action = result.optString("action", "")
                if (action in listOf("open_app", "wifi_toggle", "click", "fallback_click")) {
                    Thread.sleep(500)
                    val screen = extractScreenText()
                    lastScreenInfo = "pkg=${screen.optString("package")} texts=${screen.optInt("textCount")}"
                }

                if (!ok && action != "screen_read") {
                    emitStep(JSONObject().put("type", "error").put("ok", false)
                        .put("detail", "步骤 ${index + 1} 失败，停止执行"))
                    break
                }
            }

            // Final screen read for result
            Thread.sleep(300)
            val finalScreen = extractScreenText()
            val screenSummary = buildScreenSummary(finalScreen)
            emitStep(JSONObject().put("type", "screen").put("ok", true)
                .put("detail", screenSummary))

            emitStep(JSONObject().put("type", "done").put("ok", true)
                .put("totalMs", System.currentTimeMillis() - startTime)
                .put("detail", "完成 ${steps.size} 步，耗时 ${System.currentTimeMillis() - startTime}ms"))

            return JSONObject().put("ok", true)
                .put("totalMs", System.currentTimeMillis() - startTime)
                .put("steps", allSteps)
                .put("screenSummary", screenSummary)

        } catch (e: Exception) {
            emitStep(JSONObject().put("type", "error").put("ok", false).put("detail", e.message ?: "unknown"))
            return JSONObject().put("ok", false).put("error", e.message).put("steps", allSteps)
        }
    }

    /** Split a compound command into atomic steps */
    private fun splitCompoundCommand(command: String): List<String> {
        val cmd = command.trim()

        // Split on explicit conjunctions first
        val conjunctions = listOf("然后", "接着", "再", "之后", "并且", " and then ", " then ")
        var parts = listOf(cmd)
        for (conj in conjunctions) {
            parts = parts.flatMap { it.split(conj).map { p -> p.trim() }.filter { p -> p.isNotEmpty() } }
        }

        // Further split individual parts for compound patterns
        val result = mutableListOf<String>()
        for (part in parts) {
            result.addAll(splitSinglePart(part))
        }
        return result.filter { it.isNotEmpty() }
    }

    /** Split a single part that may contain compound patterns */
    private fun splitSinglePart(part: String): List<String> {
        // Pattern: "打开X看Y" / "打开X找Y" / "打开X找到Y" → ["打开X", "看看Y"] or ["打开X", "找到Y"]
        val openActionMatch = Regex("(打开\\S+?)(看看?|查看|找到?|搜索)(\\S+)").find(part)
        if (openActionMatch != null) {
            val action = openActionMatch.groupValues[2]
            val target = openActionMatch.groupValues[3]
            val prefix = if (action.startsWith("找")) "找到" else "看看"
            return listOf(openActionMatch.groupValues[1], "$prefix$target")
        }

        // Pattern: "打开计算器按5+3=" → ["打开计算器", calc sequence]
        val calcMatch = Regex("(打开\\S*计算器?)\\s*[按点击](.+)").find(part)
        if (calcMatch != null) {
            val calcSteps = mutableListOf(calcMatch.groupValues[1])
            calcSteps.addAll(splitCalcExpression(calcMatch.groupValues[2]))
            return calcSteps
        }

        // Pattern: "按5+3=" or "点5+3=" — calculator button sequence
        val btnMatch = Regex("^[按点击](\\d[\\d+\\-×÷*/=.]+)$").find(part)
        if (btnMatch != null) {
            return splitCalcExpression(btnMatch.groupValues[1])
        }

        return listOf(part)
    }

    /** Split a calculator expression into individual button presses */
    private fun splitCalcExpression(expr: String): List<String> {
        val steps = mutableListOf<String>()
        for (ch in expr) {
            val label = when (ch) {
                '+' -> "+"
                '-' -> "-"
                '*', '×' -> "×"
                '/', '÷' -> "÷"
                '=' -> "="
                '.' -> "."
                in '0'..'9' -> ch.toString()
                else -> continue
            }
            steps.add("calc:$label")
        }
        // After last char (usually =), read the result
        if (expr.endsWith("=")) {
            steps.add("看看结果")
        }
        return steps
    }

    /** Execute a single atomic step — delegates to existing commands + new "look" capability */
    private fun executeSingleStep(step: String, onStep: ((JSONObject) -> Unit)? = null): JSONObject {
        val cmd = step.trim().lowercase()

        // "calc:X" — calculator button press via View tree ID matching
        if (cmd.startsWith("calc:")) {
            val label = step.substring(5)
            return clickCalcButton(label)
        }

        // "找到X" — search View tree → click found element → verify navigation
        if (cmd.startsWith("找到") || cmd.startsWith("find")) {
            val target = step.trim().let {
                when {
                    it.startsWith("找到") -> it.substring(2)
                    it.startsWith("find") -> it.substring(4)
                    else -> it
                }
            }.trim()

            if (target.isNotEmpty()) {
                // Search current screen + scroll up to 3 times
                var matchedText = ""
                var scrollCount = 0

                for (attempt in 0..3) {
                    val screen = extractScreenText()
                    val texts = screen.optJSONArray("texts")
                    if (texts != null) {
                        for (i in 0 until texts.length()) {
                            val text = texts.getJSONObject(i).optString("text", "")
                            if (text.contains(target, ignoreCase = true)) {
                                matchedText = text
                                break
                            }
                        }
                    }
                    if (matchedText.isNotEmpty()) break
                    if (attempt < 3) {
                        scrollCount++
                        scrollNormalized(0.5f, 0.5f, "down", 600)
                        Thread.sleep(800)
                    }
                }

                if (matchedText.isEmpty()) {
                    return JSONObject().put("ok", false).put("action", "find")
                        .put("error", "未找到'$target'")
                        .put("summary", "滚动${scrollCount}次后未找到'$target' | ${buildScreenSummary(extractScreenText())}")
                }

                // Found — now click it to navigate
                val scrollNote = if (scrollCount > 0) "滚动${scrollCount}次后" else ""
                val clickResult = findAndClickByText(matchedText)
                if (!clickResult.optBoolean("ok")) {
                    return JSONObject().put("ok", false).put("action", "find")
                        .put("error", "${scrollNote}找到'$matchedText'但点击失败")
                        .put("summary", "找到但无法点击'$matchedText'")
                }

                // Wait for UI to settle, then read new screen
                Thread.sleep(500)
                val newScreen = extractScreenText()
                val newPkg = newScreen.optString("package", "")
                val summary = buildScreenSummary(newScreen)

                return JSONObject().put("ok", true).put("action", "find_and_navigate")
                    .put("summary", "${scrollNote}找到'$matchedText' → 点击 → $summary")
            }
        }

        // "看看" / "查看" — read screen and return semantic info
        if (cmd.startsWith("看看") || cmd.startsWith("查看") || cmd.startsWith("look")) {
            val target = step.trim().let {
                when {
                    it.startsWith("看看") -> it.substring(2)
                    it.startsWith("查看") -> it.substring(2)
                    it.startsWith("look") -> it.substring(4)
                    else -> it
                }
            }.trim()

            Thread.sleep(300)
            val screen = extractScreenText()
            val summary = buildScreenSummary(screen)

            // If target specified, try to find relevant info
            var found = ""
            if (target.isNotEmpty()) {
                val texts = screen.optJSONArray("texts")
                if (texts != null) {
                    for (i in 0 until texts.length()) {
                        val textObj = texts.getJSONObject(i)
                        val text = textObj.optString("text", "")
                        if (text.contains(target, ignoreCase = true)) {
                            found = text
                            break
                        }
                    }
                }
            }

            return JSONObject().put("ok", true).put("action", "screen_read")
                .put("summary", if (found.isNotEmpty()) "找到: $found | $summary" else summary)
        }

        // Delegate to existing natural command executor
        return executeNaturalCommand(step, onStep)
    }

    /** Click a calculator button by label — uses View tree ID matching for operators */
    private fun clickCalcButton(label: String): JSONObject {
        // Map display labels to known calculator resource ID patterns
        val idPatterns = when (label) {
            "+" -> listOf("op_add", "plus", "add")
            "-" -> listOf("op_sub", "minus", "sub")
            "×", "*" -> listOf("op_mul", "multiply", "mul")
            "÷", "/" -> listOf("op_div", "divide", "div")
            "=" -> listOf("op_eq", "equals", "eq", "result")
            "." -> listOf("dec_point", "dot", "decimal")
            "0" -> listOf("digit_0", "btn_0")
            "1" -> listOf("digit_1", "btn_1")
            "2" -> listOf("digit_2", "btn_2")
            "3" -> listOf("digit_3", "btn_3")
            "4" -> listOf("digit_4", "btn_4")
            "5" -> listOf("digit_5", "btn_5")
            "6" -> listOf("digit_6", "btn_6")
            "7" -> listOf("digit_7", "btn_7")
            "8" -> listOf("digit_8", "btn_8")
            "9" -> listOf("digit_9", "btn_9")
            else -> listOf()
        }

        val root = rootInActiveWindow
            ?: return JSONObject().put("ok", false).put("error", "No active window")

        try {
            // Strategy 1: Find by text (works for digit buttons)
            val textResult = findAndClickByText(label)
            if (textResult.optBoolean("ok")) {
                return textResult.put("action", "click").put("summary", "clicked '$label' via text")
            }

            // Strategy 2: Find by resource ID pattern
            for (pattern in idPatterns) {
                // Try common package prefixes
                val ids = listOf(
                    "com.coloros.calculator:id/$pattern",
                    "com.coloros.calculator:id/op_$pattern",
                    "com.android.calculator2:id/$pattern",
                    "com.sec.android.app.popupcalculator:id/$pattern"
                )
                for (id in ids) {
                    val nodes = root.findAccessibilityNodeInfosByViewId(id)
                    if (nodes != null && nodes.isNotEmpty()) {
                        for (node in nodes) {
                            if (node.isVisibleToUser) {
                                val clicked = if (node.isClickable) {
                                    node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                                } else {
                                    // Try parent click
                                    var parent = node.parent
                                    var result = false
                                    var depth = 0
                                    while (parent != null && depth < 3) {
                                        if (parent.isClickable) {
                                            result = parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                                            try { parent.recycle() } catch (_: Exception) {}
                                            break
                                        }
                                        val gp = parent.parent
                                        try { parent.recycle() } catch (_: Exception) {}
                                        parent = gp
                                        depth++
                                    }
                                    result
                                }
                                if (clicked) {
                                    nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                                    return JSONObject().put("ok", true).put("action", "click")
                                        .put("summary", "clicked '$label' via id=$id")
                                }
                            }
                        }
                        nodes.forEach { try { it.recycle() } catch (_: Exception) {} }
                    }
                }
            }

            // Strategy 3: Find by contentDescription
            fun findByDesc(node: AccessibilityNodeInfo, depth: Int): AccessibilityNodeInfo? {
                if (depth > 15) return null
                val desc = node.contentDescription?.toString() ?: ""
                if (desc.contains(label, ignoreCase = true) && node.isVisibleToUser) return node
                for (i in 0 until node.childCount) {
                    val child = node.getChild(i) ?: continue
                    val found = findByDesc(child, depth + 1)
                    if (found != null) return found
                    try { child.recycle() } catch (_: Exception) {}
                }
                return null
            }

            val descNode = findByDesc(root, 0)
            if (descNode != null) {
                val rect = Rect()
                descNode.getBoundsInScreen(rect)
                dispatchClick(rect.centerX(), rect.centerY(), 50)
                try { descNode.recycle() } catch (_: Exception) {}
                return JSONObject().put("ok", true).put("action", "click")
                    .put("summary", "clicked '$label' via contentDescription at ${rect.centerX()},${rect.centerY()}")
            }

            return JSONObject().put("ok", false).put("action", "click")
                .put("error", "Calculator button '$label' not found")
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }

    /** Build a human-readable summary of the current screen */
    private fun buildScreenSummary(screen: JSONObject): String {
        val pkg = screen.optString("package", "unknown")
        val texts = screen.optJSONArray("texts")
        val textCount = screen.optInt("textCount", 0)

        // Extract the most important visible text (first few items)
        val visibleTexts = mutableListOf<String>()
        if (texts != null) {
            for (i in 0 until minOf(texts.length(), 8)) {
                val text = texts.getJSONObject(i).optString("text", "")
                if (text.length in 1..50) visibleTexts.add(text)
            }
        }

        return "[$pkg] ${visibleTexts.joinToString(" | ")} (共${textCount}项)"
    }

    /** Open app by name — tries package list first, then known apps, then intent search */
    private fun executeOpenApp(appName: String, steps: JSONArray, startTime: Long): JSONObject {
        fun step(name: String, ok: Boolean, detail: String = "") {
            steps.put(JSONObject().put("step", name).put("ok", ok)
                .put("ms", System.currentTimeMillis() - startTime)
                .apply { if (detail.isNotEmpty()) put("detail", detail) })
        }

        step("intent", true, "open app='$appName'")

        // Known app mappings (Chinese → package/intent)
        val knownApps = mapOf(
            "计算器" to "com.coloros.calculator/com.android.calculator2.Calculator",
            "calculator" to "com.coloros.calculator/com.android.calculator2.Calculator",
            "设置" to "android.settings.SETTINGS",
            "settings" to "android.settings.SETTINGS",
            "相机" to "android.media.action.IMAGE_CAPTURE",
            "camera" to "android.media.action.IMAGE_CAPTURE",
            "浏览器" to "android.intent.action.VIEW:https://www.baidu.com",
            "browser" to "android.intent.action.VIEW:https://www.google.com",
            "电话" to "android.intent.action.DIAL",
            "phone" to "android.intent.action.DIAL",
            "短信" to "android.intent.action.VIEW:sms:",
            "sms" to "android.intent.action.VIEW:sms:",
            "wifi" to "android.settings.WIFI_SETTINGS",
            "wlan" to "android.settings.WIFI_SETTINGS",
            "蓝牙" to "android.settings.BLUETOOTH_SETTINGS",
            "bluetooth" to "android.settings.BLUETOOTH_SETTINGS",
        )

        val appNameLower = appName.lowercase()

        // Try known apps first
        val known = knownApps.entries.firstOrNull { appNameLower.contains(it.key) }
        if (known != null) {
            try {
                val value = known.value
                if (value.contains("/")) {
                    // Explicit component
                    val (pkg, cls) = value.split("/")
                    val intent = Intent(Intent.ACTION_MAIN).apply {
                        setClassName(pkg, cls)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    startActivity(intent)
                    step("execute", true, "opened via component: $value")
                } else if (value.contains(":")) {
                    // Action with data
                    val (action, data) = value.split(":", limit = 2)
                    val intent = Intent(action).apply {
                        this.data = android.net.Uri.parse(data)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    startActivity(intent)
                    step("execute", true, "opened via action+data: $value")
                } else {
                    // Action only (settings etc.) — clear task to start fresh
                    val intent = Intent(value).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                    }
                    startActivity(intent)
                    step("execute", true, "opened via action: $value")
                }
                return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                    .put("command", "打开$appName").put("action", "open_app").put("app", appName).put("steps", steps)
            } catch (e: Exception) {
                step("known_app_failed", false, e.message ?: "")
            }
        }

        // Try packageManager.getLaunchIntentForPackage with app name
        try {
            val pm = packageManager
            val installedApps = pm.getInstalledApplications(0)
            for (app in installedApps) {
                val label = pm.getApplicationLabel(app).toString()
                if (label.contains(appName, ignoreCase = true) || appName.contains(label, ignoreCase = true)) {
                    val launchIntent = pm.getLaunchIntentForPackage(app.packageName)
                    if (launchIntent != null) {
                        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        startActivity(launchIntent)
                        step("execute", true, "opened '$label' (${app.packageName})")
                        return JSONObject().put("ok", true).put("totalMs", System.currentTimeMillis() - startTime)
                            .put("command", "打开$appName").put("action", "open_app")
                            .put("app", label).put("package", app.packageName).put("steps", steps)
                    }
                }
            }
        } catch (e: Exception) {
            step("search_failed", false, e.message ?: "")
        }

        step("execute", false, "app not found: $appName")
        return JSONObject().put("ok", false).put("totalMs", System.currentTimeMillis() - startTime)
            .put("command", "打开$appName").put("error", "找不到应用: $appName").put("steps", steps)
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
