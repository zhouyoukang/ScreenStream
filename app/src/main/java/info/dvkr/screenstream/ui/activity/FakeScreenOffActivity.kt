package info.dvkr.screenstream.ui.activity

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import android.view.Gravity
import android.widget.FrameLayout
import android.graphics.drawable.ColorDrawable
import com.elvishew.xlog.XLog

public class FakeScreenOffActivity : Activity() {

    private lateinit var gestureDetector: GestureDetector

    @SuppressLint("ClickableViewAccessibility")
    override public fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        XLog.d("[FakeScreenOffActivity] onCreate")
        info.dvkr.screenstream.input.InputService.isScreenOffMode = true

        // 1. Set window flags
        // FLAG_NOT_TOUCHABLE: Allows touches to pass through to the app behind
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN)
        window.addFlags(WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE)
        
        // Ensure window itself is transparent
        window.setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
        
        // 2. Set brightness to ABSOLUTE minimum
        val params = window.attributes
        params.screenBrightness = 0.0f 
        window.attributes = params

        // 3. Create a semi-transparent black layout (Alpha 245 = ~96% opacity)
        // Compromise: Very Dark (looks off), requires extreme boost on client.
        val frameLayout = FrameLayout(this)
        frameLayout.setBackgroundColor(Color.argb(245, 0, 0, 0))
        
        // Add a hint text
        val hintText = TextView(this)
        hintText.text = "Screen Off Active\nPress Back or Web Toggle to Wake"
        hintText.gravity = Gravity.CENTER
        hintText.setTextColor(Color.LTGRAY) 
        hintText.textSize = 14f
        hintText.alpha = 0.7f 
        val layoutParams = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT, 
            FrameLayout.LayoutParams.WRAP_CONTENT
        )
        layoutParams.gravity = Gravity.CENTER
        frameLayout.addView(hintText, layoutParams)
        
        setContentView(frameLayout)

        // 4. Hide system bars
        window.decorView.systemUiVisibility = (View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_FULLSCREEN)
    }

    override fun onNewIntent(intent: android.content.Intent?) {
        super.onNewIntent(intent)
        XLog.d("[FakeScreenOffActivity] onNewIntent: Toggling off")
        finish()
    }

    override public fun onDestroy() {
        XLog.d("[FakeScreenOffActivity] onDestroy")
        info.dvkr.screenstream.input.InputService.isScreenOffMode = false
        super.onDestroy()
    }
}
