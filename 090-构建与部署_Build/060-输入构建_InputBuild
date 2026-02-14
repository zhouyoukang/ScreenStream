plugins {
    alias(libs.plugins.androidLibrary)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.parcelize)
    alias(libs.plugins.kotlin.compose)
}

kotlin {
    explicitApi()
    jvmToolchain(17)
}

android {
    namespace = "info.dvkr.screenstream.input"
    compileSdk = rootProject.extra["compileSdkVersion"] as Int
    buildToolsVersion = rootProject.extra["buildToolsVersion"] as String

    defaultConfig {
        minSdk = rootProject.extra["minSdkVersion"] as Int
    }

    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation(projects.common)

    // Ktor for HTTP API server
    implementation(libs.ktor.server.cio)
    implementation(libs.ktor.server.content.negotiation)
    implementation(libs.ktor.serialization.kotlinx.json)
    implementation(libs.ktor.server.cors)
}
