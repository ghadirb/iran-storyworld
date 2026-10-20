plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "ir.ghadirb.riwayatiran"
    compileSdk = 34

    defaultConfig {
        applicationId = "ir.ghadirb.riwayatiran"
        minSdk = 24
        targetSdk = 34
        versionCode = (System.getenv("APP_VERSION_CODE") ?: "1").toInt()
        versionName = System.getenv("APP_VERSION_NAME") ?: "0.1.0"
    }

    // امضای نسخهٔ نهایی فقط وقتی فعال می‌شود که کلید از طریق متغیرهای محیطی (GitHub Secrets) داده شده باشد.
    val ksPath = System.getenv("KEYSTORE_PATH")
    signingConfigs {
        if (ksPath != null && file(ksPath).exists()) {
            create("release") {
                storeFile = file(ksPath)
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }

    androidResources { noCompress += listOf("mp4", "json", "jpg") }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.2")
    implementation("androidx.media3:media3-exoplayer:1.3.1")
    implementation("androidx.media3:media3-ui:1.3.1")
}
