#!/usr/bin/env python3
"""پیش‌نمایش تدوین‌شدهٔ قسمت ۲، نسخهٔ ۲. خروجی: out/ep02_preview_v2.mp4"""
import glob, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "assets", "audio")
IMAGES = os.path.join(ROOT, "assets", "images")
VIDEOS = os.path.join(ROOT, "assets", "video")
OUT = os.path.join(ROOT, "out")
TMP = os.path.join(OUT, "ep02_v2_tmp")
WIDTH, HEIGHT, FPS = 1280, 720, 24
DIALOGUE_GAP, VOICE_TAIL, TRANSITION = 0.42, 0.45, 0.20
VIDEO_ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p"]

# فایل 30 با نام اشتباه «20.بعضی‌ها...» ذخیره شده است؛ نام موجود را حفظ می‌کنیم.
TIMELINE = {
    "s01": (["20.صبح", "21."], "08.png", "08.mp4"),
    "s02": (["22.", "23."], "09.png", "09.mp4"),
    "s03": (["24.", "25.", "26."], "10.png", "10.mp4"),
    "s04": (["27.", "28."], "11.png", None),
    "s05": (["29.", "20.بعضی", "31.", "32."], "12.png", None),
    "s06": (["33.", "34.", "35."], "13.png", "13.mp4"),
}

def run(*args):
    subprocess.run(args, check=True)

def duration(path):
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", path
    ], text=True).strip())

def find_unique(folder, pattern, label):
    matches = sorted(glob.glob(os.path.join(folder, pattern)))
    if len(matches) != 1:
        raise RuntimeError(f"{label}: انتظار یک فایل بود، پیدا شد {len(matches)}: {matches}")
    return matches[0]

def audio_file(prefix):
    return find_unique(AUDIO, prefix + "*.mp3", f"فایل روایت با پیشوند {prefix!r}")

def make_silence(path, seconds):
    run("ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", path)

def normalized_voice(source, target):
    # همهٔ خطوط پیش از اتصال به PCM یکسان تبدیل می‌شوند تا اختلاف codec خطا نسازد.
    run("ffmpeg", "-y", "-i", source, "-vn", "-ar", "44100", "-ac", "2",
        "-c:a", "pcm_s16le", target)

def image_video(image_path, out_path, seconds):
    frames = max(1, round(seconds * FPS))
    filt = (
        f"scale=1600:900:force_original_aspect_ratio=increase,crop=1600:900,"
        f"zoompan=z='min(1.045,1+0.045*on/{frames})':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"setsar=1,fade=t=in:st=0:d=0.18,"
        f"fade=t=out:st={max(0, seconds-TRANSITION):.3f}:d={TRANSITION}"
    )
    run("ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", image_path,
        "-vf", filt, "-t", f"{seconds:.3f}", *VIDEO_ENCODE, "-an", out_path)

def clip_video(clip_path, out_path, seconds, temp_prefix):
    clip_duration = duration(clip_path)
    head = temp_prefix + "_head.mp4"
    filt = (
        f"[0:v]split[bg0][fg0];"
        f"[bg0]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},boxblur=24:4[bg];"
        f"[fg0]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={FPS},fade=t=in:st=0:d=0.18[v]"
    )
    run("ffmpeg", "-y", "-i", clip_path, "-filter_complex", filt,
        "-map", "[v]", "-t", f"{min(clip_duration, seconds):.3f}",
        *VIDEO_ENCODE, "-an", head)
    if seconds <= clip_duration + 0.03:
        if seconds < clip_duration - 0.03:
            run("ffmpeg", "-y", "-i", head, "-t", f"{seconds:.3f}",
                "-vf", f"fade=t=out:st={max(0, seconds-TRANSITION):.3f}:d={TRANSITION}",
                *VIDEO_ENCODE, "-an", out_path)
        else:
            os.replace(head, out_path)
        return

    # اگر روایت از کلیپ بلندتر بود، آخرین فریم مکث می‌کند تا صدا بریده نشود.
    last = temp_prefix + "_last.png"
    run("ffmpeg", "-y", "-sseof", "-0.08", "-i", clip_path,
        "-frames:v", "1", "-update", "1", last)
    rest = seconds - clip_duration
    tail = temp_prefix + "_tail.mp4"
    frames = max(1, round(rest * FPS))
    run("ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", last,
        "-vf", f"scale={WIDTH}:{HEIGHT},zoompan=z='min(1.035,1+0.035*on/{frames})':"
               f"d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1,"
               f"fade=t=out:st={max(0, rest-TRANSITION):.3f}:d={TRANSITION}",
        "-t", f"{rest:.3f}", *VIDEO_ENCODE, "-an", tail)
    listing = temp_prefix + "_concat.txt"
    with open(listing, "w", encoding="utf-8") as f:
        f.write(f"file '{head}'\nfile '{tail}'\n")
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listing,
        "-t", f"{seconds:.3f}", *VIDEO_ENCODE, "-an", out_path)

def main():
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    silence = os.path.join(TMP, "gap.wav")
    make_silence(silence, DIALOGUE_GAP)
    scene_videos, scene_starts, report = [], {}, []
    elapsed = 0.0

    for scene_id, (prefixes, image_name, clip_name) in TIMELINE.items():
        scene_audio_list = os.path.join(TMP, f"{scene_id}_audio.txt")
        with open(scene_audio_list, "w", encoding="utf-8") as f:
            for index, prefix in enumerate(prefixes):
                source = audio_file(prefix)
                normalized = os.path.join(TMP, f"{scene_id}_line_{index+1:02d}.wav")
                normalized_voice(source, normalized)
                f.write(f"file '{normalized}'\n")
                if index < len(prefixes) - 1:
                    f.write(f"file '{silence}'\n")

        voice = os.path.join(TMP, f"{scene_id}_voice.wav")
        run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", scene_audio_list,
            "-ar", "44100", "-ac", "2", "-af", f"apad=pad_dur={VOICE_TAIL}", voice)
        voice_duration = duration(voice)
        video = os.path.join(TMP, f"{scene_id}_video.mp4")
        if clip_name:
            clip_video(os.path.join(VIDEOS, clip_name), video, voice_duration,
                       os.path.join(TMP, scene_id))
            visual = "کلیپ + مکث آخرین فریم در صورت نیاز"
        else:
            image_video(os.path.join(IMAGES, image_name), video, voice_duration)
            visual = "تصویر با حرکت آرام"

        muxed = os.path.join(TMP, f"{scene_id}.mp4")
        run("ffmpeg", "-y", "-i", video, "-i", voice, "-map", "0:v:0", "-map", "1:a:0",
            "-t", f"{voice_duration:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", muxed)
        scene_starts[scene_id] = elapsed
        elapsed += voice_duration
        scene_videos.append(muxed)
        report.append({"scene": scene_id, "seconds": round(voice_duration, 2),
                       "visual": visual, "audio_files": prefixes})

    concat_list = os.path.join(TMP, "scenes.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for path in scene_videos:
            f.write(f"file '{path}'\n")
    voice_video = os.path.join(TMP, "ep02_voice_only.mp4")
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", voice_video)
    total = duration(voice_video)

    music = os.path.join(AUDIO, "موسیقی بی‌کلام.wav")
    ambience = os.path.join(AUDIO, "محیط کارگاه.wav")
    hammer = os.path.join(AUDIO, "صدای چکش.wav")
    for path in (music, ambience, hammer):
        if not os.path.isfile(path):
            raise FileNotFoundError(f"فایل صوتی لازم پیدا نشد: {path}")

    hammer_delay_ms = int((scene_starts["s02"] + 2.0) * 1000)
    fade_out_start = max(0.0, total - 2.0)
    output = os.path.join(OUT, "ep02_preview_v2.mp4")
    mix = (
        "[1:a]volume=0.16,afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={fade_out_start:.3f}:d=2[music0];"
        "[music0][0:a]sidechaincompress=threshold=0.025:ratio=5:attack=25:release=350[music];"
        "[2:a]volume=0.075[ambience];"
        f"[3:a]volume=0.16,adelay={hammer_delay_ms}|{hammer_delay_ms}[hammer];"
        "[0:a]volume=1.0[voice];"
        "[voice][music][ambience][hammer]amix=inputs=4:duration=first:dropout_transition=2,"
        "loudnorm=I=-18:TP=-1.5:LRA=11,alimiter=limit=0.95[aout]"
    )
    run("ffmpeg", "-y", "-i", voice_video, "-stream_loop", "-1", "-i", music,
        "-stream_loop", "-1", "-i", ambience, "-i", hammer, "-filter_complex", mix,
        "-map", "0:v:0", "-map", "[aout]", "-t", f"{total:.3f}", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output)

    final_duration = duration(output)
    report_path = os.path.join(OUT, "ep02_preview_v2_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "episode": "ch01-ep02", "status": "preview",
            "output": "ep02_preview_v2.mp4", "duration_seconds": round(final_duration, 2),
            "scene_start_seconds": {k: round(v, 2) for k, v in scene_starts.items()},
            "scenes": report,
            "mix": {
                "music": "موسیقی بی‌کلام.wav، کم‌حجم با کاهش خودکار هنگام گفتار",
                "ambience": "محیط کارگاه.wav، کم‌حجم در سراسر ویدئو",
                "sfx": "صدای چکش.wav، یک‌بار در نمای دوم با سطح صدای کم"
            },
            "limitations": [
                "پیش‌نمایش هنوز نیازمند تماشای انسانی و بررسی هماهنگی تصویر و گفتار است.",
                "افکت اختصاصی قدم، برس روی سنگ و باد جداگانه در مخزن موجود نیست؛ افکت تازه‌ای جعل نشده است.",
                "داستان و ادعاهای تاریخی همچنان پیش‌نویس تأییدنشده‌اند."
            ]
        }, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"مدت نهایی: {final_duration:.2f} ثانیه")
    print(f"خروجی: {output}")
    print(f"گزارش: {report_path}")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ساخت پیش‌نمایش ناموفق بود: {exc}", file=sys.stderr)
        sys.exit(1)
