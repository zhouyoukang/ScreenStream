pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven("https://www.jitpack.io")
    }
}

rootProject.name = "ScreenStream_v2"

// 新的功能模块结构
include(":app")
project(":app").projectDir = file("010-用户界面与交互_UI")

include(":common")
project(":common").projectDir = file("070-基础设施_Infrastructure")

include(":mjpeg")
project(":mjpeg").projectDir = file("020-投屏链路_Streaming/010-MJPEG投屏_MJPEG")

include(":rtsp")
project(":rtsp").projectDir = file("020-投屏链路_Streaming/020-RTSP投屏_RTSP")

include(":webrtc")
project(":webrtc").projectDir = file("020-投屏链路_Streaming/030-WebRTC投屏_WebRTC")

include(":input")
project(":input").projectDir = file("040-反向控制_Input")
