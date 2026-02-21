plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose.compiler)
    alias(libs.plugins.kotlin.parcelize)
}

android {
    namespace = "info.dvkr.screenstream.mjpeg"
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

    buildFeatures {
        compose = true
        buildConfig = true
    }

    androidResources {
        ignoreAssetsPattern = "!dev:!*.md"
    }

    sourceSets {
        getByName("main") {
            java.setSrcDirs(listOf("mjpeg"))
            assets.setSrcDirs(listOf("assets", "mjpeg/assets"))
            res.setSrcDirs(listOf("res", "mjpeg/res"))
        }
    }
}

dependencies {
    implementation(project(":common"))
    implementation(project(":input"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)

    implementation(libs.koin.android)
    implementation(libs.koin.androidx.compose)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.ktor.server.core)
    implementation(libs.ktor.server.cio)
    implementation(libs.ktor.server.cors)
    implementation(libs.ktor.server.status.pages)
    implementation(libs.ktor.server.compression)
    implementation(libs.ktor.server.caching.headers)
    implementation(libs.ktor.server.default.headers)
    implementation(libs.ktor.server.forwarded.header)
    implementation(libs.ktor.server.websockets)
}
