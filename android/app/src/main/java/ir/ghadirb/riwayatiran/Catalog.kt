package ir.ghadirb.riwayatiran

import android.content.Context
import org.json.JSONObject

data class Episode(
    val id: String,
    val number: Int,
    val title: String,
    val summary: String,
    val video: String,
    val poster: String,
    val parentsReal: String,
    val parentsStory: String,
)

data class Chapter(
    val id: String,
    val title: String,
    val subtitle: String,
    val available: Boolean,
    val episodes: List<Episode>,
)

object Catalog {
    /** ابتدا آخرین نسخهٔ دریافت‌شده؛ در نبود آن، کاتالوگ سبک داخل برنامه. */
    fun load(ctx: Context): List<Chapter> {
        val cached = java.io.File(ctx.filesDir, "catalog.json")
        val text = if (cached.exists()) cached.readText(Charsets.UTF_8)
        else ctx.assets.open("catalog.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
        return try { parse(text) } catch (e: Exception) {
            parse(ctx.assets.open("catalog.json").bufferedReader(Charsets.UTF_8).use { it.readText() })
        }
    }

    /** کاتالوگ را آنلاین می‌گیرد، اگر معتبر بود ذخیره می‌کند و فهرست تازه را برمی‌گرداند. */
    suspend fun refresh(ctx: Context): List<Chapter>? {
        val text = Net.fetchCatalogText() ?: return null
        val parsed = try { parse(text) } catch (e: Exception) { return null }
        java.io.File(ctx.filesDir, "catalog.json").writeText(text, Charsets.UTF_8)
        return parsed
    }

    fun parse(text: String): List<Chapter> {
        val chapters = JSONObject(text).getJSONArray("chapters")
        return (0 until chapters.length()).map { i ->
            val c = chapters.getJSONObject(i)
            val eps = c.optJSONArray("episodes")
            Chapter(
                id = c.getString("id"),
                title = c.getString("title"),
                subtitle = c.optString("subtitle"),
                available = c.optBoolean("available", false),
                episodes = if (eps == null) emptyList() else (0 until eps.length()).map { j ->
                    val e = eps.getJSONObject(j)
                    Episode(
                        id = e.getString("id"),
                        number = e.getInt("number"),
                        title = e.getString("title"),
                        summary = e.optString("summary"),
                        video = e.getString("video"),
                        poster = e.optString("poster"),
                        parentsReal = e.optString("parentsReal"),
                        parentsStory = e.optString("parentsStory"),
                    )
                },
            )
        }
    }
}

/** فقط روی خود دستگاه ذخیره می‌شود؛ هیچ اطلاعاتی ارسال نمی‌شود. */
class Progress(ctx: Context) {
    private val sp = ctx.getSharedPreferences("progress", Context.MODE_PRIVATE)
    fun watched(): Set<String> = sp.getStringSet("watched", emptySet())?.toSet() ?: emptySet()
    fun markWatched(id: String) {
        sp.edit().putStringSet("watched", watched() + id).apply()
    }
}
