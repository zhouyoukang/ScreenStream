package com.github.audiocenter.receiver

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var etTargetIp: EditText
    private lateinit var btnStart: Button
    private lateinit var btnStop: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        etTargetIp = findViewById(R.id.etTargetIp)
        btnStart = findViewById(R.id.btnStart)
        btnStop = findViewById(R.id.btnStop)

        // Request Notification Permission for Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 101)
            }
        }

        btnStart.setOnClickListener {
            val ip = etTargetIp.text.toString()
            if (ip.isBlank()) {
                Toast.makeText(this, "Please enter IP", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            startListening(ip)
        }

        btnStop.setOnClickListener {
            stopListening()
        }
    }

    private fun startListening(ip: String) {
        val intent = Intent(this, PlayerService::class.java).apply {
            putExtra(PlayerService.EXTRA_IP, ip)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        Toast.makeText(this, "Service Started", Toast.LENGTH_SHORT).show()
    }

    private fun stopListening() {
        val intent = Intent(this, PlayerService::class.java).apply {
            action = PlayerService.ACTION_STOP
        }
        startService(intent) // Send stop command
        Toast.makeText(this, "Service Stopped", Toast.LENGTH_SHORT).show()
    }
}
