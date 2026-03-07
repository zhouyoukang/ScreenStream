package com.ffalcon.mars.android.sdk.demo

import android.app.Application
import com.ffalcon.mars.android.sdk.MarsSDK


class MarsDemoApplication : Application() {
    companion object {
        lateinit var appContext: Application
    }

    override fun onCreate() {
        super.onCreate()
        appContext = this
        MarsSDK.init(this)
    }
}