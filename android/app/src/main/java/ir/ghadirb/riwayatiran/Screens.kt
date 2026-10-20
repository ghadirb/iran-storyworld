package ir.ghadirb.riwayatiran

import android.graphics.BitmapFactory
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
import androidx.media3.common.MediaItem
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
    val chapters = remember { Catalog.load(ctx) }
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
                            val ep = ch.episodes[idx]
                            val next = ch.episodes.getOrNull(idx + 1)
                            BackHandler { screen = "chapter:${ch.id}" }
                            PlayerScreen(
                                ep, next,
                                onBack = { screen = "chapter:${ch.id}" },
                                onWatched = { progress.markWatched(it); watched = progress.watched() },
                                onNext = { screen = "play:${ch.id}:${it.id}" },
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
                        Text("$done از ${ch.episodes.size} قسمت دیده شد", color = Sand, fontSize = 13.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun EpisodesScreen(ch: Chapter, watched: Set<String>, onBack: () -> Unit, onPick: (Episode) -> Unit) {
    Column(Modifier.fillMaxSize().background(Sand).padding(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("‹ بازگشت", color = Brown, fontSize = 16.sp) }
            Spacer(Modifier.weight(1f))
        }
        Text(ch.title, color = Brown, fontSize = 30.sp, fontWeight = FontWeight.Bold)
        Text(ch.subtitle, color = Lapis, fontSize = 15.sp)
        Spacer(Modifier.height(12.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(ch.episodes) { ep ->
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp))
                        .background(Color.White).clickable { onPick(ep) }.padding(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Poster(ep.poster, Modifier.width(150.dp).aspectRatio(16f / 9f).clip(RoundedCornerShape(12.dp)))
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text("قسمت ${ep.number}", color = Lapis, fontSize = 13.sp)
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
private fun Poster(path: String, modifier: Modifier) {
    val ctx = LocalContext.current
    val bmp = remember(path) {
        try { ctx.assets.open(path).use { BitmapFactory.decodeStream(it) }?.asImageBitmap() } catch (e: Exception) { null }
    }
    if (bmp != null) Image(bmp, null, modifier, contentScale = ContentScale.Crop)
    else Box(modifier.background(Brown))
}

@Composable
private fun PlayerScreen(
    ep: Episode,
    next: Episode?,
    onBack: () -> Unit,
    onWatched: (String) -> Unit,
    onNext: (Episode) -> Unit,
) {
    val ctx = LocalContext.current
    var ended by remember(ep.id) { mutableStateOf(false) }
    var showParents by remember { mutableStateOf(false) }
    val player = remember(ep.id) {
        ExoPlayer.Builder(ctx).build().apply {
            setMediaItem(MediaItem.fromUri("asset:///" + ep.video))
            prepare()
            playWhenReady = true
        }
    }
    DisposableEffect(player) {
        val l = object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_ENDED) { ended = true; onWatched(ep.id) }
            }
        }
        player.addListener(l)
        onDispose { player.removeListener(l); player.release() }
    }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle, player) {
        val o = LifecycleEventObserver { _, e -> if (e == Lifecycle.Event.ON_STOP) player.pause() }
        lifecycle.addObserver(o)
        onDispose { lifecycle.removeObserver(o) }
    }

    Column(Modifier.fillMaxSize().background(Brown)) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("‹ بازگشت", color = Gold, fontSize = 16.sp) }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { showParents = true }) { Text("ⓘ والدین", color = Sand, fontSize = 14.sp) }
        }
        AndroidView(
            factory = { PlayerView(it).apply { this.player = player; useController = true } },
            update = { it.player = player },
            modifier = Modifier.fillMaxWidth().aspectRatio(16f / 9f),
        )
        Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("قسمت ${ep.number}: ${ep.title}", color = Gold, fontSize = 20.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
            if (ended) {
                Spacer(Modifier.height(16.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(onClick = { ended = false; player.seekTo(0); player.play() },
                        colors = ButtonDefaults.buttonColors(containerColor = Sand, contentColor = Brown)) { Text("↻ دوباره") }
                    if (next != null) Button(onClick = { onNext(next) },
                        colors = ButtonDefaults.buttonColors(containerColor = Gold, contentColor = Brown)) { Text("قسمت بعد ›") }
                    else Button(onClick = onBack,
                        colors = ButtonDefaults.buttonColors(containerColor = Gold, contentColor = Brown)) { Text("به‌زودی قسمت‌های بیشتر") }
                }
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
