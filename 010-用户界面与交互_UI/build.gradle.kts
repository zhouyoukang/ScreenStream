plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose.compiler)
}

android {
    namespace = "info.dvkr.screenstream"
    compileSdk = 36

    defaultConfig {
        applicationId = "info.dvkr.screenstream"
        minSdk = 24
        targetSdk = 36
        versionCode = 42010
        versionName = "4.2.10"
    }

    signingConfigs {
        getByName("debug") {
            storeFile = file("../gradle/debug-key.jks")
            storePassword = "debug_key_password"
            keyAlias = "debug_key_alias"
            keyPassword = "debug_key_password"
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("debug")
            applicationIdSuffix = ".dev"
            versionNameSuffix = "-dev"
        }
        release {
            isMinifyEnabled = false
        }
    }

    flavorDimensions += "app"
    productFlavors {
        create("FDroid") {
            dimension = "app"
            manifestPlaceholders += mapOf("adMobPubId" to "")
        }
        create("PlayStore") {
            dimension = "app"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    sourceSets {
        getByName("main") {
            java.setSrcDirs(listOf(
                "010-主界面_MainUI",
                "020-设置界面_SettingsUI",
                "030-通知系统_Notifications",
                "040-瓦片服务_Tiles",
                "050-通用组件_CommonUI",
                "../070-基础设施_Infrastructure/040-日志系统_Logging"
            ))
            manifest.srcFile("010-主界面_MainUI/AndroidManifest.xml")
            res.setSrcDirs(listOf("010-主界面_MainUI/res"))
        }
        // FDroid and PlayStore flavor source sets omitted - no flavor-specific sources
        // getByName("FDroid") { java.setSrcDirs(listOf("010-主界面_MainUI/FDroid")) }
        // getByName("PlayStore") { java.setSrcDirs(listOf("010-主界面_MainUI/PlayStore")) }
    }
}

dependencies {
    implementation(project(":common"))
    implementation(project(":mjpeg"))
    implementation(project(":input"))

    "PlayStoreImplementation"(project(":rtsp"))
    "PlayStoreImplementation"(project(":webrtc"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.core.splashscreen)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.window)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material3.adaptive)
    implementation(libs.androidx.compose.material3.adaptive.navigation.suite)
    implementation(libs.androidx.compose.material3.adaptive.layout)
    implementation(libs.androidx.compose.material3.adaptive.navigation)
    implementation(libs.koin.android)

    implementation(libs.processPhoenix)

    implementation(libs.shizuku.api)
    implementation(libs.shizuku.provider)
}
