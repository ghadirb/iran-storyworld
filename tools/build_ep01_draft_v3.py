#!/usr/bin/env python3
"""Build episode 1 preview v3 by mixing the three generated WAV tracks into v2.
Keeps ep01_draft.mp4 and ep01_draft_v2.mp4 unchanged.
"""
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "assets", "audio")
OUT = os.path.join(ROOT, "out")
V2 = os.path.join(OUT, "ep01_draft_v2.mp4")
FINAL = os.path.join(OUT, "ep01_draft_v3.mp4")

# Must match the scene order and dialogue order in build_ep01_draft_v2.py.
TIMELINE = [
    [1],
    [2, 3, 4],
    [5, 6, 7],
    [8, 9, 10, 11],
    [12, 18, 13, 14],
    [17, 15, 16],
]
GAP = 0.35
TAIL = 0.5


def run(*args):
    subprocess.run(args, check=True)


def duration(path):
    value = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path
    ], text=True).strip()
    return float(value)


def required_file(name):
    path = os.path.join(A, name)
    if not os.path.isfile(path):
        sys.exit(f"Required audio file not found: {path}")
    return path


def voice_file(number):
    matches = glob.glob(os.path.join(A, f"{number:02d}.*.mp3"))
    if not matches:
        sys.exit(f"Narration audio {number:02d} not found in {A}")
    return matches[0]


def main():
    os.makedirs(OUT, exist_ok=True)

    # Build v2 first; the v2 output itself is not overwritten.
    run(sys.executable, os.path.join(ROOT, "tools", "build_ep01_draft_v2.py"))
    music = required_file("موسیقی بی‌کلام.wav")
    ambience = required_file("محیط کارگاه.wav")
    hammer = required_file("صدای چکش.wav")

    video_duration = duration(V2)
    # Calculate the start of scene 4 from actual narration file lengths.
    scene_durations = []
    for numbers in TIMELINE:
        d = sum(duration(voice_file(n)) for n in numbers)
        d += GAP * max(0, len(numbers) - 1) + TAIL
        scene_durations.append(d)
    scene4_start = sum(scene_durations[:3])
    hammer_start = min(scene4_start + 1.0, max(0.0, video_duration - 1.0))
    hammer_delay_ms = int(hammer_start * 1000)
    fade_out_start = max(0.0, video_duration - 3.0)

    # Music is ducked under narration; ambience is intentionally subtle.
    # The hammer SFX is placed in the stoneworking scene, not across the whole film.
    filters = (
        "[0:a]aresample=44100,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[voice];"
        f"[1:a]aresample=44100,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
        f"volume=0.12,afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start:.3f}:d=3[music];"
        "[music][voice]sidechaincompress=threshold=0.025:ratio=8:attack=20:release=500[musicduck];"
        f"[2:a]aresample=44100,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
        f"volume=0.07,atrim=duration={video_duration:.3f}[ambience];"
        f"[3:a]aresample=44100,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
        f"volume=0.22,adelay={hammer_delay_ms}|{hammer_delay_ms},apad,"
        f"atrim=duration={video_duration:.3f}[hammer];"
        "[voice][musicduck][ambience][hammer]amix=inputs=4:duration=first:dropout_transition=2:normalize=0,"
        "alimiter=limit=0.95[aout]"
    )

    run(
        "ffmpeg", "-y",
        "-i", V2,
        "-stream_loop", "-1", "-i", music,
        "-stream_loop", "-1", "-i", ambience,
        "-i", hammer,
        "-filter_complex", filters,
        "-map", "0:v:0", "-map", "[aout]",
        "-t", f"{video_duration:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        FINAL
    )
    print(f"Created {FINAL} ({video_duration:.1f} seconds)")
    print(f"Scene 4 hammer effect starts at {hammer_start:.1f} seconds")


if __name__ == "__main__":
    main()
