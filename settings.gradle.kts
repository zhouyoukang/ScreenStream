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
project(":app").projectDir = file("用户界面")

include(":common")
project(":common").projectDir = file("基础设施")

include(":mjpeg")
project(":mjpeg").projectDir = file("投屏链路/MJPEG投屏")

include(":rtsp")
project(":rtsp").projectDir = file("投屏链路/RTSP投屏")

include(":webrtc")
project(":webrtc").projectDir = file("投屏链路/WebRTC投屏")

include(":input")
project(":input").projectDir = file("反向控制")
