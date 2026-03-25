plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose.compiler)
    alias(libs.plugins.kotlin.parcelize)
}

android {
    namespace = "info.dvkr.screenstream.common"
    compileSdk = 36

    defaultConfig {
        minSdk = 21
        consumerProguardFiles("consumer-rules.pro")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
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
                "010-模块管理_ModuleManager",
                "020-依赖注入_DI",
                "030-通用工具_Utils",
                "../010-用户界面与交互_UI/050-通用组件_CommonUI",
                "../010-用户界面与交互_UI/030-通知系统_Notifications/010-通用通知_CommonNotifications",
                "../080-配置管理_Settings/010-全局配置_GlobalSettings"
            ))

            res.setSrcDirs(listOf(
                "../010-用户界面与交互_UI/050-通用组件_CommonUI/res"
            ))
        }
    }
}

dependencies {
    api(libs.kotlinStdlibJdk8)
    api(libs.kotlinReflect)
    api(libs.kotlinx.coroutines.android)

    api(libs.androidx.core.ktx)
    api(libs.androidx.activity.compose)
    api(libs.androidx.fragment)
    api(libs.androidx.appcompat)
    api(libs.androidx.lifecycle.runtime.compose)
    api(libs.androidx.window)
    api(libs.androidx.datastore.preferences)

    api(platform(libs.androidx.compose.bom))
    api(libs.androidx.compose.ui)
    api(libs.androidx.compose.material3)
    api(libs.androidx.compose.material3.window)

    api(libs.koin.android)
    api(libs.koin.androidx.compose)

    api(libs.xlog)

    implementation(libs.nayuki.qrcodegen)
}
