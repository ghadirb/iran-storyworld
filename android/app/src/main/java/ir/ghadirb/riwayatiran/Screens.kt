package ir.ghadirb.riwayatiran

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.graphics.BitmapFactory
import android.net.Uri
import android.media.AudioManager
import android.provider.Settings
import android.view.WindowManager
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import kotlin.math.abs
import kotlin.math.roundToInt
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.annotation.OptIn
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.ResolvingDataSource
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView

private val Sand = Color(0xFFF4E4C8)
private val Brown = Color(0xFF3B2A1A)
private val Gold = Color(0xFFE9B872)
private val Lapis = Color(0xFF1F3F7A)

@Composable
fun AppRoot() {
    val ctx = LocalContext.current
    var chapters by remember { mutableStateOf(Catalog.load(ctx)) }
    LaunchedEffect(Unit) { Catalog.refresh(ctx)?.let { chapters = it } }
    val progress = remember { Progress(ctx) }
    var watched by remember { mutableStateOf(progress.watched()) }
    // "home" | "chapter:<id>" | "play:<chapterId>:<episodeId>"
    var screen by rememberSaveable { mutableStateOf("home") }

    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
        MaterialTheme {
            Surface(Modifier.fillMaxSize(), color = Sand) {
                val parts = screen.split(":")
                when (parts[0]) {
                    "chapter" -> {
                        val ch = chapters.firstOrNull { it.id == parts[1] }
                        if (ch == null) screen = "home" else {
                            BackHandler { screen = "home" }
                            EpisodesScreen(ch, watched, onBack = { screen = "home" }) { ep ->
                                screen = "play:${ch.id}:${ep.id}"
                            }
                        }
                    }
                    "play" -> {
                        val ch = chapters.firstOrNull { it.id == parts[1] }
                        val idx = ch?.episodes?.indexOfFirst { it.id == parts[2] } ?: -1
                        if (ch == null || idx < 0) screen = "home" else {
                            BackHandler { screen = "chapter:${ch.id}" }
                            PlayerScreen(
                                ch, idx, progress,
                                onBack = { screen = "chapter:${ch.id}" },
                                onWatched = { progress.markWatched(it); watched = progress.watched() },
                            )
                        }
                    }
                    else -> HomeScreen(chapters, watched,
                        onOpen = { screen = "chapter:${it.id}" },
                        onContinue = { ch, ep -> screen = "play:${ch.id}:${ep.id}" })
                }
            }
        }
    }
}

@Composable
private fun HomeScreen(
    chapters: List<Chapter>,
    watched: Set<String>,
    onOpen: (Chapter) -> Unit,
    onContinue: (Chapter, Episode) -> Unit,
) {
    val first = chapters.firstOrNull { it.available }
    val nextEp = first?.episodes?.firstOrNull { it.id !in watched } ?: first?.episodes?.firstOrNull()
    Column(
        Modifier.fillMaxSize().background(Brown).padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(24.dp))
        Text("روایت ایران", color = Gold, fontSize = 38.sp, fontWeight = FontWeight.Bold)
        Text("داستان‌هایی از ایران قدیم", color = Sand, fontSize = 16.sp)
        Spacer(Modifier.height(20.dp))

        if (first != null && nextEp != null) {
            val label = if (watched.isEmpty()) "شروع ماجرا" else "ادامهٔ ماجرا"
            Button(
                onClick = { onContinue(first, nextEp) },
                colors = ButtonDefaults.buttonColors(containerColor = Gold, contentColor = Brown),
                modifier = Modifier.fillMaxWidth().height(64.dp),
                shape = RoundedCornerShape(32.dp),
            ) { Text("▶  $label", fontSize = 22.sp, fontWeight = FontWeight.Bold) }
            Spacer(Modifier.height(20.dp))
        }

        LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(chapters) { ch ->
                val shape = RoundedCornerShape(20.dp)
                Column(
                    Modifier.fillMaxWidth().clip(shape)
                        .background(if (ch.available) Lapis else Color(0xFF5A4630))
                        .let { if (ch.available) it.clickable { onOpen(ch) } else it }
                        .padding(18.dp),
                ) {
                    Text(
                        (if (ch.available) "" else "🔒  ") + ch.title,
                        color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold,
                    )
                    Text(ch.subtitle, color = Gold, fontSize = 15.sp)
                    if (ch.available) {
                        val done = ch.episodes.count { it.id in watched }
                        Text("$done از ${ch.episodes.size} بخش دیده شد", color = Sand, fontSize = 13.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun EpisodesScreen(ch: Chapter, watched: Set<String>, onBack: () -> Unit, onPick: (Episode) -> Unit) {
    val allDone = ch.episodes.isNotEmpty() && ch.episodes.all { it.id in watched }
    val startEp = if (allDone) ch.episodes.firstOrNull() else ch.episodes.firstOrNull { it.id !in watched }
    val label = when {
        allDone -> "↻  دیدن دوبارهٔ داستان"
        ch.episodes.any { it.id in watched } -> "▶  ادامهٔ داستان"
        else -> "▶  شروع داستان"
    }
    Column(Modifier.fillMaxSize().background(Sand).padding(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("‹ بازگشت", color = Brown, fontSize = 16.sp) }
            Spacer(Modifier.weight(1f))
        }
        Text(ch.title, color = Brown, fontSize = 30.sp, fontWeight = FontWeight.Bold)
        Text(ch.subtitle, color = Lapis, fontSize = 15.sp)
        Spacer(Modifier.height(12.dp))
        if (startEp != null) {
            Button(
                onClick = { onPick(startEp) },
                colors = ButtonDefaults.buttonColors(containerColor = Lapis, contentColor = Color.White),
                modifier = Modifier.fillMaxWidth().height(60.dp),
                shape = RoundedCornerShape(30.dp),
            ) { Text(label, fontSize = 20.sp, fontWeight = FontWeight.Bold) }
            Text(
                "${ch.episodes.size} بخش پشت‌سرهم، بدون وقفه",
                color = Color(0xFF6B5B45), fontSize = 13.sp,
                modifier = Modifier.padding(top = 6.dp, bottom = 8.dp).align(Alignment.CenterHorizontally),
            )
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(ch.episodes) { ep ->
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp))
                        .background(Color.White).clickable { onPick(ep) }.padding(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Poster(ep.id, Modifier.width(150.dp).aspectRatio(16f / 9f).clip(RoundedCornerShape(12.dp)))
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text("بخش ${ep.number}", color = Lapis, fontSize = 13.sp)
                        Text(ep.title, color = Brown, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                        Text(ep.summary, color = Color(0xFF6B5B45), fontSize = 13.sp)
                        if (ep.id in watched) Text("✓ دیده شد", color = Color(0xFF2E7D32), fontSize = 13.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun Poster(episodeId: String, modifier: Modifier) {
    val ctx = LocalContext.current
    val bmp by produceState<androidx.compose.ui.graphics.ImageBitmap?>(null, episodeId) {
        value = Net.poster(ctx, episodeId)?.asImageBitmap()
    }
    val b = bmp
    if (b != null) Image(b, null, modifier, contentScale = ContentScale.Crop)
    else Box(modifier.background(Brown))
}

/** همهٔ بخش‌های یک فصل پشت‌سرهم پخش می‌شوند؛ لینک امضاشدهٔ هر بخش درست لحظهٔ بازشدن گرفته می‌شود. */
@OptIn(UnstableApi::class)
@Composable
private fun PlayerScreen(
    ch: Chapter,
    startIndex: Int,
    progress: Progress,
    onBack: () -> Unit,
    onWatched: (String) -> Unit,
) {
    val ctx = LocalContext.current
    val parts = remember(ch.id) { ch.episodes }
    var cur by remember(ch.id) { mutableStateOf(startIndex.coerceIn(0, parts.lastIndex)) }
    val ep = parts[cur.coerceIn(0, parts.lastIndex)]
    var ended by remember(ch.id) { mutableStateOf(false) }
    var showParents by remember { mutableStateOf(false) }
    var hud by remember { mutableStateOf<String?>(null) }
    val pvRef = remember { arrayOfNulls<PlayerView>(1) }
    val activity = remember(ctx) { ctx.findActivity() }
    val audio = remember(ctx) { ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager }
    DisposableEffect(Unit) {
        onDispose { setBrightness(activity, WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE) }
    }
    val player = remember(ch.id) {
        val http = DefaultHttpDataSource.Factory().setConnectTimeoutMs(15_000).setReadTimeoutMs(20_000)
        val resolving = ResolvingDataSource.Factory(http, ResolvingDataSource.Resolver { spec ->
            val id = spec.uri.host ?: spec.uri.toString()
            spec.withUri(Uri.parse(Net.playUrlBlocking(id)))
        })
        ExoPlayer.Builder(ctx).setMediaSourceFactory(DefaultMediaSourceFactory(resolving)).build()
    }
    var loadFailed by remember(ch.id) { mutableStateOf(false) }
    LaunchedEffect(ch.id) {
        player.setMediaItems(parts.map {
            MediaItem.Builder().setUri("riwayat://${it.id}").setMediaId(it.id).setMimeType(MimeTypes.VIDEO_MP4).build()
        })
        val r = progress.resume(ch.id)
        val start = startIndex.coerceIn(0, parts.lastIndex)
        player.seekTo(start, if (r != null && r.first == start) r.second else 0L)
        player.prepare()
        player.playWhenReady = true
    }
    DisposableEffect(player) {
        val l = object : Player.Listener {
            override fun onMediaItemTransition(item: MediaItem?, reason: Int) {
                val i = player.currentMediaItemIndex
                if (reason == Player.MEDIA_ITEM_TRANSITION_REASON_AUTO) parts.getOrNull(i - 1)?.let { onWatched(it.id) }
                cur = i
            }
            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_ENDED) {
                    parts.lastOrNull()?.let { onWatched(it.id) }
                    progress.clearResume(ch.id)
                    ended = true
                }
                if (state == Player.STATE_READY) { ended = false; loadFailed = false }
            }
            override fun onPlayerError(error: PlaybackException) { loadFailed = true }
        }
        player.addListener(l)
        onDispose {
            if (!ended) progress.saveResume(ch.id, player.currentMediaItemIndex, player.currentPosition)
            player.removeListener(l); player.release()
        }
    }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle, player) {
        val o = LifecycleEventObserver { _, e ->
            if (e == Lifecycle.Event.ON_STOP) {
                player.pause()
                if (!ended) progress.saveResume(ch.id, player.currentMediaItemIndex, player.currentPosition)
            }
        }
        lifecycle.addObserver(o)
        onDispose { lifecycle.removeObserver(o) }
    }

    Column(Modifier.fillMaxSize().background(Brown)) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("‹ بازگشت", color = Gold, fontSize = 16.sp) }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { showParents = true }) { Text("ⓘ والدین", color = Sand, fontSize = 14.sp) }
        }
        Box(Modifier.fillMaxWidth().aspectRatio(16f / 9f)) {
            AndroidView(
                factory = { PlayerView(it).apply { this.player = player; useController = true; pvRef[0] = this } },
                update = { it.player = player },
                modifier = Modifier.fillMaxSize(),
            )
            if (loadFailed) {
                Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("برای دیدن داستان به اینترنت نیاز است.", color = Sand, fontSize = 15.sp)
                    TextButton(onClick = { loadFailed = false; player.prepare(); player.play() }) { Text("تلاش دوباره", color = Gold, fontSize = 16.sp) }
                }
            }
            // لایهٔ حرکات: نوار کنترل پایین آزاد می‌ماند
            Box(
                Modifier.fillMaxSize().padding(bottom = 64.dp)
                    .pointerInput(ep.id) {
                        detectTapGestures(onTap = {
                            pvRef[0]?.let { v -> if (v.isControllerFullyVisible) v.hideController() else v.showController() }
                        })
                    }
                    .pointerInput(ep.id) {
                        // 0 نامشخص، 1 جلو/عقب، 2 صدا (راست)، 3 نور (چپ)
                        var mode = 0
                        var startX = 0f
                        var accX = 0f
                        var accY = 0f
                        var volStart = 0f
                        var briStart = 0.5f
                        var seekStart = 0L
                        var seekTarget = 0L
                        detectDragGestures(
                            onDragStart = { o -> mode = 0; startX = o.x; accX = 0f; accY = 0f },
                            onDragEnd = { if (mode == 1) player.seekTo(seekTarget); hud = null; mode = 0 },
                            onDragCancel = { hud = null; mode = 0 },
                        ) { change, drag ->
                            change.consume()
                            accX += drag.x
                            accY += drag.y
                            val w = size.width.toFloat()
                            val h = size.height.toFloat()
                            if (mode == 0) {
                                if (abs(accX) < 14f && abs(accY) < 14f) return@detectDragGestures
                                mode = if (abs(accX) > abs(accY)) 1 else if (startX > w / 2f) 2 else 3
                                when (mode) {
                                    1 -> { seekStart = player.currentPosition; seekTarget = seekStart }
                                    2 -> volStart = audio.getStreamVolume(AudioManager.STREAM_MUSIC).toFloat()
                                    3 -> briStart = currentBrightness(activity)
                                }
                            }
                            when (mode) {
                                1 -> {
                                    val dur = player.duration
                                    val maxPos = if (dur > 0) dur else Long.MAX_VALUE
                                    seekTarget = (seekStart + accX / w * 60000f).toLong().coerceIn(0L, maxPos)
                                    hud = (if (seekTarget >= seekStart) "⏩ " else "⏪ ") + fmtTime(seekTarget)
                                }
                                2 -> {
                                    val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                                    val v = (volStart + (-accY / h) * max * 1.5f).coerceIn(0f, max.toFloat())
                                    audio.setStreamVolume(AudioManager.STREAM_MUSIC, v.roundToInt(), 0)
                                    hud = "🔊 ${(v / max * 100f).roundToInt()}٪"
                                }
                                3 -> {
                                    val b = (briStart + (-accY / h) * 1.5f).coerceIn(0.02f, 1f)
                                    setBrightness(activity, b)
                                    hud = "☀ ${(b * 100f).roundToInt()}٪"
                                }
                            }
                        }
                    },
            )
            hud?.let {
                Box(
                    Modifier.align(Alignment.Center)
                        .background(Color(0xAA000000), RoundedCornerShape(16.dp))
                        .padding(horizontal = 18.dp, vertical = 10.dp),
                ) { Text(it, color = Color.White, fontSize = 22.sp) }
            }
        }
        Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("${ch.title} — بخش ${cur + 1} از ${parts.size}", color = Sand.copy(alpha = 0.8f), fontSize = 13.sp, textAlign = TextAlign.Center)
            Text(ep.title, color = Gold, fontSize = 20.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                parts.forEachIndexed { i, p ->
                    val isCur = i == cur
                    Box(
                        Modifier.size(40.dp).clip(RoundedCornerShape(20.dp))
                            .background(if (isCur) Gold else if (p.id in progress.watched()) Sand.copy(alpha = 0.55f) else Sand.copy(alpha = 0.2f))
                            .clickable { ended = false; player.seekToDefaultPosition(i); player.play() },
                        contentAlignment = Alignment.Center,
                    ) { Text("${i + 1}", color = if (isCur) Brown else Sand, fontWeight = FontWeight.Bold) }
                }
            }
            Spacer(Modifier.height(6.dp))
            Text("کشیدن روی تصویر: راست = صدا، چپ = نور، چپ/راست = جلو و عقب", color = Sand.copy(alpha = 0.7f), fontSize = 12.sp, textAlign = TextAlign.Center)
            if (ended) {
                Spacer(Modifier.height(16.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(onClick = { ended = false; player.seekToDefaultPosition(0); player.play() },
                        colors = ButtonDefaults.buttonColors(containerColor = Sand, contentColor = Brown)) { Text("↻ دوباره از اول") }
                    Button(onClick = onBack,
                        colors = ButtonDefaults.buttonColors(containerColor = Gold, contentColor = Brown)) { Text("بازگشت") }
                }
                Text("فصل‌های بعدی به‌زودی می‌آیند", color = Sand.copy(alpha = 0.7f), fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp))
            }
        }
    }

    if (showParents) {
        AlertDialog(
            onDismissRequest = { showParents = false },
            confirmButton = { TextButton(onClick = { showParents = false }) { Text("بستن") } },
            title = { Text("گوشهٔ والدین و معلم‌ها") },
            text = {
                Column {
                    Text("واقعی است:", fontWeight = FontWeight.Bold)
                    Text(ep.parentsReal)
                    Spacer(Modifier.height(10.dp))
                    Text("تخیلی یا بازسازی هنری است:", fontWeight = FontWeight.Bold)
                    Text(ep.parentsStory)
                }
            },
        )
    }
}


private fun Context.findActivity(): Activity? {
    var c: Context = this
    while (c is ContextWrapper) {
        if (c is Activity) return c
        c = c.baseContext
    }
    return null
}

private fun currentBrightness(a: Activity?): Float {
    val cur = a?.window?.attributes?.screenBrightness ?: -1f
    if (cur >= 0f) return cur
    return try {
        Settings.System.getInt(a!!.contentResolver, Settings.System.SCREEN_BRIGHTNESS) / 255f
    } catch (e: Exception) { 0.5f }
}

private fun setBrightness(a: Activity?, v: Float) {
    a?.window?.let { w ->
        val lp = w.attributes
        lp.screenBrightness = v
        w.attributes = lp
    }
}

private fun fmtTime(ms: Long): String {
    val s = (ms / 1000).toInt()
    return "%d:%02d".format(s / 60, s % 60)
}
