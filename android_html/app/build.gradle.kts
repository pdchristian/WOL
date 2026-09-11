// WOL Manager (HTML/WebView-Variante): dünne native Hülle + JS-Bridge.
// Bewusst OHNE Compose — die komplette UI steckt in app/src/main/assets/app/.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "de.wolmanager.html"
    compileSdk = 34

    defaultConfig {
        applicationId = "de.wolmanager.html"
        minSdk = 26
        targetSdk = 34
        versionCode = 6
        versionName = "2.3.5"
    }

    buildTypes {
        debug {
            // Debug-Build ohne Signatur-Probleme: Standardschlüssel vom SDK
        }
        release {
            isMinifyEnabled = false
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
        buildConfig = true
    }

    // HTML/JS/CSS aus dem assets-Ordner nie komprimieren (lädt sonst schneller/sauber)
    androidResources {
        noCompress("html", "css", "js", "json")
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.2")
    implementation("androidx.webkit:webkit:1.11.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
}
