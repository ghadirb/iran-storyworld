package ir.ghadirb.riwayatiran

import android.content.Context
import android.graphics.BitmapFactory
import android.graphics.Bitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** ارتباط با Worker کلودفلر: کاتالوگ، پوستر، و لینک پخش امضاشدهٔ کوتاه‌مدت. */
object Net {
    private fun open(path: String, withKey: Boolean = false): HttpURLConnection =
        (URL(BuildConfig.API_BASE.trimEnd('/') + path).openConnection() as HttpURLConnection).apply {
            connectTimeout = 10_000
            readTimeout = 15_000
            if (withKey) setRequestProperty("X-App-Key", BuildConfig.APP_KEY)
        }

    suspend fun fetchCatalogText(): String? = withContext(Dispatchers.IO) {
        try {
            val c = open("/catalog.json")
            if (c.responseCode == 200) c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() } else null
        } catch (e: Exception) { null }
    }

    /** لینک پخش با عمر ≈ ۱۰ دقیقه؛ هر بار پخش دوباره گرفته می‌شود. */
    suspend fun playUrl(episodeId: String): String? = withContext(Dispatchers.IO) {
        try {
            val c = open("/play/$episodeId", withKey = true)
            if (c.responseCode == 200) JSONObject(c.inputStream.bufferedReader().use { it.readText() }).getString("url") else null
        } catch (e: Exception) { null }
    }

    suspend fun poster(ctx: Context, episodeId: String): Bitmap? = withContext(Dispatchers.IO) {
        val f = File(File(ctx.cacheDir, "posters").apply { mkdirs() }, "$episodeId.jpg")
        try {
            if (!f.exists()) {
                val c = open("/poster/$episodeId.jpg")
                if (c.responseCode == 200) c.inputStream.use { i -> f.outputStream().use { o -> i.copyTo(o) } }
            }
            if (f.exists()) BitmapFactory.decodeFile(f.path) else null
        } catch (e: Exception) { null }
    }
}
