pluginManagement {
    repositories {
        maven { url = uri("file:///C:/Program Files/Android/Android Studio/plugins/android/lib") }
        maven { url = uri("file:///C:/Program Files/Android/Android Studio/plugins/gradle/lib") }
        maven { url = uri("file:///C:/Program Files/Android/Android Studio/lib") }
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("com.android.application") version "8.1.0" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
}

rootProject.name = "ULTRON"
include(":app")
