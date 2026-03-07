package com.ffalcon.mars.android.sdk.demo

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.RequiresApi
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.ffalcon.mars.android.sdk.actionbutton.EventFromSource
import com.ffalcon.mars.android.sdk.actionbutton.KeyClickListener
import com.ffalcon.mars.android.sdk.actionbutton.ReceiverKeyEventManager
import com.ffalcon.mars.android.sdk.demo.databinding.LayoutDemoHomeBinding
import com.ffalcon.mars.android.sdk.touch.TempleAction
import com.ffalcon.mars.android.sdk.ui.activity.BaseEventActivity
import com.ffalcon.mars.android.sdk.util.BlinkTypeConstant
import com.ffalcon.mars.android.sdk.util.FLogger
import com.ffalcon.mars.android.sdk.util.FixPosFocusTracker
import com.ffalcon.mars.android.sdk.util.FocusHolder
import com.ffalcon.mars.android.sdk.util.FocusInfo
import com.ffalcon.mars.android.sdk.util.LedBroadcastUtils
import com.ffalcon.mars.android.sdk.util.PriorityLevelConstant
import com.ffalcon.mars.android.sdk.util.SoundEffect
import kotlinx.coroutines.launch
import java.io.File


class DemoHomeActivity : BaseEventActivity() {
    private lateinit var binding: LayoutDemoHomeBinding
    private var fixPosFocusTracker: FixPosFocusTracker? = null
    private lateinit var receiverKeyEventManager: ReceiverKeyEventManager

    @RequiresApi(Build.VERSION_CODES.S)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = LayoutDemoHomeBinding.inflate(layoutInflater)
        setContentView(binding.root)
        initFocusTarget()
        initEvent()

        var currentLedId: Int = LedBroadcastUtils.INVALID_INDEX
        receiverKeyEventManager = ReceiverKeyEventManager(this,
            object : KeyClickListener {
                override fun onClick(source: EventFromSource, keyCode: Int) {
                    FLogger.d("onClick")
                    currentLedId = LedBroadcastUtils.setLedEffectByApp(
                        100, 20, 20,
                        BlinkTypeConstant.BLINK_TYPE_SPECIAL_LIGHTING_RECORDING_CALL,
                        PriorityLevelConstant.PRIORITY_MIDDLE,
                        0
                    )
                }

                override fun onLongClick(source: EventFromSource, keyCode: Int) {
                    FLogger.d("onLongClick")
                    LedBroadcastUtils.offLedByApp(currentLedId)
                }
            }).apply {
            startObserve()
        }


        val receiver = MyReceiver()
        val filter = IntentFilter("com.rayneo.aispeech.wakeup")
        registerReceiver(receiver, filter)

    }

    class MyReceiver : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            // 在这里处理接收到的广播
            FLogger.d("111111111111111111")
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        receiverKeyEventManager.stopObserve()
    }

    private fun initFocusTarget() {
        val focusHolder = FocusHolder(false)

        focusHolder.addFocusTarget(
            FocusInfo(
                binding.btn1,
                eventHandler = { action ->
                    when (action) {
                        is TempleAction.Click -> {
                            Log.d("DemoHomeActivity", "btn1 Click")
                        }

                        is TempleAction.DoubleClick -> {
                            Log.d("DemoHomeActivity", "btn1 DoubleClick")
                        }

                        is TempleAction.TripleClick -> {
                            Log.d("DemoHomeActivity", "btn1 TripleClick")
                        }

                        is TempleAction.LongClick -> {
                            Log.d("DemoHomeActivity", "btn1 LongClick")
                        }

                        else -> Unit
                    }
                },
                focusChangeHandler = { hasFocus ->
                    triggerFocus(hasFocus, binding.btn1)
                }
            ),
            FocusInfo(
                binding.btn2,
                eventHandler = { action ->
                    when (action) {
                        is TempleAction.Click -> {
                            Log.d("DemoHomeActivity", "btn2 Click")
                        }

                        else -> Unit
                    }
                },
                focusChangeHandler = { hasFocus ->
                    triggerFocus(hasFocus, binding.btn2)
                }
            ),
            FocusInfo(
                binding.btn3,
                eventHandler = { action ->
                    when (action) {
                        is TempleAction.Click -> {
                            Log.d("DemoHomeActivity", "btn3 Click")
                        }

                        else -> Unit
                    }
                },
                focusChangeHandler = { hasFocus ->
                    triggerFocus(hasFocus, binding.btn3)
                }
            ),
            FocusInfo(
                binding.btn4,
                eventHandler = { action ->
                    when (action) {
                        is TempleAction.Click -> {
                            Log.d("DemoHomeActivity", "btn4 Click")
                            scanQRCodeAndConnectWifi()
                        }

                        else -> Unit
                    }
                },
                focusChangeHandler = { hasFocus ->
                    triggerFocus(hasFocus, binding.btn4)
                }
            )
        )
        focusHolder.currentFocus(binding.btn1)

        fixPosFocusTracker = FixPosFocusTracker(focusHolder).apply {
            focusObj.hasFocus = true
        }


    }


    //v3没有屏幕，看不见视图，这里只是方便调试
    private fun triggerFocus(hasFocus: Boolean, view: View) {
        view.setBackgroundColor(getColor(if (hasFocus) R.color.purple_200 else R.color.black))
    }

    private fun initEvent() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.RESUMED) {
                templeActionViewModel.state.collect {
                    fixPosFocusTracker?.handleFocusTargetEvent(it)
                }
            }
        }
    }

    private fun connectToWifi(wifiManager: WifiManager, ssid: String, password: String) {
        // 连接到特定的 Wi-Fi 网络
        val networkId = addNetwork(wifiManager, ssid, password)

        if (networkId != -1) {
            wifiManager.enableNetwork(networkId, true)
        }
    }

    private fun addNetwork(wifiManager: WifiManager, ssid: String, password: String): Int {
        val wifiConfiguration = WifiConfiguration().apply {
            SSID = "\"$ssid\""
            preSharedKey = "\"$password\""
        }

        return wifiManager.addNetwork(wifiConfiguration)
    }


    private val scanResultLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == RESULT_OK) {
                val data = result.data
                val scannedResult = data?.getStringExtra("SCAN_RESULT")
                Log.d("DemoHomeActivity", "scannedResult:$scannedResult")
                //"$ssid;$password"
                scannedResult?.let {
                    val wifiInfo = it.split(";")
                    if (wifiInfo.size == 2) {
                        val wifiManager = getSystemService(Context.WIFI_SERVICE) as WifiManager

                        if (!wifiManager.isWifiEnabled) {
                            wifiManager.isWifiEnabled = true
                        }

                        connectToWifi(
                            wifiManager,
                            wifiInfo[0],
                            wifiInfo[1]
                        )
                    }
                }

            }
        }

    private fun scanQRCodeAndConnectWifi() {
        val intent = Intent(this, CameraScanActivity::class.java)
        scanResultLauncher.launch(intent)
    }

}