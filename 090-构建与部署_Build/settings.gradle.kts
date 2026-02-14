pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.8.0"
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

enableFeaturePreview("TYPESAFE_PROJECT_ACCESSORS")

rootProject.name = "ScreenStream"

include(":app")
project(":app").projectDir = file("01-应用与界面_app")

include(":common")
project(":common").projectDir = file("02-基础设施_common")

include(":mjpeg")
project(":mjpeg").projectDir = file("03-投屏输出_MJPEG")

include(":rtsp")
project(":rtsp").projectDir = file("03-投屏输出_RTSP")

include(":webrtc")
project(":webrtc").projectDir = file("03-投屏输出_WebRTC")

include(":input")
project(":input").projectDir = file("04-反向控制_Input")