package com.github.audiocenter

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.text.format.Formatter
import android.widget.Button
import android.widget.EditText
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var etTargetIp: EditText
    private lateinit var tvIpAddress: TextView
    private lateinit var btnSourceStart: Button
    private lateinit var btnReceiverStart: Button
    private lateinit var btnReceiverStop: Button
    
    private lateinit var rgAudioSource: RadioGroup
    private lateinit var rbMic: RadioButton
    private lateinit var rbSystem: RadioButton

    private lateinit var mediaProjectionManager: MediaProjectionManager

    // Activity Result for Media Projection
    private val mediaProjectionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            startSourceServiceSDK29(result.resultCode, result.data!!)
        } else {
            Toast.makeText(this, "Screen Capture Permission Denied", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        tvIpAddress = findViewById(R.id.tvIpAddress)
        etTargetIp = findViewById(R.id.etTargetIp)
        btnSourceStart = findViewById(R.id.btnSourceStart)
        btnReceiverStart = findViewById(R.id.btnReceiverStart)
        btnReceiverStop = findViewById(R.id.btnReceiverStop)
        
        rgAudioSource = findViewById(R.id.rgAudioSource)
        rbMic = findViewById(R.id.rbMic)
        rbSystem = findViewById(R.id.rbSystem)

        updateIpAddress()
        
        // Android 10+ Check for System Audio
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            mediaProjectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            rbSystem.isEnabled = true
        } else {
            rbSystem.isEnabled = false
            rbSystem.text = "System Audio (Android 10+)"
        }

        // --- SOURCE LOGIC ---
        btnSourceStart.setOnClickListener {
            if (rbMic.isChecked) {
                // Microphone Source
                if (checkPermission(Manifest.permission.RECORD_AUDIO)) {
                    val intent = Intent(this, AudioStreamingService::class.java).apply {
                        putExtra(AudioStreamingService.EXTRA_SOURCE_TYPE, AudioStreamingService.SOURCE_MIC)
                    }
                    startServiceCompat(intent)
                    Toast.makeText(this, "Mic Source Started (Port 8085)", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this, "Mic Permission Required", Toast.LENGTH_SHORT).show()
                    requestPermissions()
                }
            } else {
                // System Audio Source (SDK 29+)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    // Launch MediaProjection permission request
                    val captureIntent = mediaProjectionManager.createScreenCaptureIntent()
                    mediaProjectionLauncher.launch(captureIntent)
                }
            }
        }

        // --- RECEIVER LOGIC ---
        btnReceiverStart.setOnClickListener {
            val ip = etTargetIp.text.toString()
            if (ip.isNotBlank()) {
                val intent = Intent(this, PlayerService::class.java).apply {
                    putExtra(PlayerService.EXTRA_IP, ip)
                }
                startServiceCompat(intent)
                Toast.makeText(this, "Listening to $ip", Toast.LENGTH_SHORT).show()
            }
        }

        btnReceiverStop.setOnClickListener {
            val intent = Intent(this, PlayerService::class.java).apply {
                action = PlayerService.ACTION_STOP
            }
            startService(intent)
            Toast.makeText(this, "Receiver Stopped", Toast.LENGTH_SHORT).show()
        }
    }
    
    private fun startSourceServiceSDK29(resultCode: Int, data: Intent) {
         val intent = Intent(this, AudioStreamingService::class.java).apply {
            putExtra(AudioStreamingService.EXTRA_SOURCE_TYPE, AudioStreamingService.SOURCE_SYSTEM)
            putExtra(AudioStreamingService.EXTRA_RESULT_CODE, resultCode)
            putExtra(AudioStreamingService.EXTRA_RESULT_DATA, data)
        }
        startServiceCompat(intent)
        Toast.makeText(this, "System Audio Source Started", Toast.LENGTH_SHORT).show()
    }

    private fun startServiceCompat(intent: Intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun updateIpAddress() {
        val wifiManager = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
        val ipAddress = Formatter.formatIpAddress(wifiManager.connectionInfo.ipAddress)
        tvIpAddress.text = "IP: $ipAddress"
    }

    private fun checkPermission(permission: String): Boolean {
        return ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED
    }

    private fun requestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.FOREGROUND_SERVICE
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        ActivityCompat.requestPermissions(this, permissions.toTypedArray(), 100)
    }
}
