package com.ffalcon.mars.android.sdk.demo

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Bundle
import android.util.Log
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat

import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.ffalcon.mars.android.sdk.demo.databinding.ActivityCameraScanBinding
import com.ffalcon.mars.android.sdk.touch.TempleAction
import com.ffalcon.mars.android.sdk.ui.activity.BaseEventActivity
import com.ffalcon.mars.android.sdk.util.SoundEffect
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import kotlinx.coroutines.launch
import java.io.IOException
import java.util.concurrent.Executors


class CameraScanActivity : BaseEventActivity() {
    private lateinit var binding: ActivityCameraScanBinding

    // 创建一个单线程执行器用于图像分析（避免阻塞主线程）
    private val analysisExecutor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCameraScanBinding.inflate(layoutInflater)
        setContentView(binding.root)
        startCamera()
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.RESUMED) {
                templeActionViewModel.state.collect {
                    when (it) {
                        is TempleAction.DoubleClick -> {
                            finish()
                        }

                        else -> Unit
                    }
                }
            }
        }
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)

        cameraProviderFuture.addListener({
            // 相机提供者准备就绪后执行
            val cameraProvider: ProcessCameraProvider = cameraProviderFuture.get()

            // 创建预览用例
           /* val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(binding.previewView.surfaceProvider)
            }*/

            // 创建图像分析用例
            val imageAnalysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST) // 只处理最新的帧，避免积压
                .build()

            // 创建二维码扫描器实例，只识别QR码
            val scanner = BarcodeScanning.getClient(
                com.google.mlkit.vision.barcode.BarcodeScannerOptions.Builder()
                    .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
                    .build()
            )

            // 设置分析器
            imageAnalysis.setAnalyzer(analysisExecutor, QrCodeAnalyzer(scanner) { barcodes ->
                SoundEffect.LocalSoundEffect(R.raw.finish).play()
                // 这个Lambda会在主线程被调用，用于更新UI
                runOnUiThread {
                    processScanResult(barcodes)
                }
            })

            // 选择后置摄像头
            val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

            try {
                // 解绑所有用例后再绑定新的
                cameraProvider.unbindAll()
                // 将用例绑定到生命周期
                cameraProvider.bindToLifecycle(
                    this as LifecycleOwner,
                    cameraSelector,
                   // preview,
                    imageAnalysis
                )
            } catch (e: Exception) {
                Log.e("CameraScanActivity", "用例绑定失败: ${e.message}")
            }
        }, ContextCompat.getMainExecutor(this))
    }


    /**
     * 处理扫描结果
     */
    private fun processScanResult(barcodes: List<Barcode>) {
        if (barcodes.isNotEmpty()) {
            val barcode = barcodes.first() // 取第一个检测到的二维码
            val rawValue = barcode.rawValue ?: ""
            Log.d("CameraScanActivity", "processScanResult:$rawValue")
            val intent = Intent()
            intent.putExtra("SCAN_RESULT", rawValue)
            setResult(RESULT_OK, intent)
            finish()
        }
    }

    /**
     * 自定义图像分析器
     */
    inner class QrCodeAnalyzer(
        private val scanner: BarcodeScanner,
        private val onDetection: (List<Barcode>) -> Unit
    ) : ImageAnalysis.Analyzer {

        @SuppressLint("UnsafeOptInUsageError")
        override fun analyze(imageProxy: ImageProxy) {
            val mediaImage = imageProxy.image
            if (mediaImage != null) {
                // 创建InputImage对象，并传入图像旋转信息
                val image = com.google.mlkit.vision.common.InputImage.fromMediaImage(
                    mediaImage,
                    imageProxy.imageInfo.rotationDegrees
                )

                // 处理图像
                scanner.process(image)
                    .addOnSuccessListener { barcodes ->
                        // 检测成功，将结果回调出去
                        if (barcodes.isNotEmpty()) {
                            onDetection(barcodes)
                        }
                    }
                    .addOnFailureListener { e ->
                        Log.e("QrCodeAnalyzer", "识别失败: ${e.message}")
                    }
                    .addOnCompleteListener {
                        // 无论成功与否，都必须关闭ImageProxy释放资源！
                        imageProxy.close()
                    }
            } else {
                imageProxy.close()
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // 关闭执行器，释放资源
        analysisExecutor.shutdown()
    }


}

