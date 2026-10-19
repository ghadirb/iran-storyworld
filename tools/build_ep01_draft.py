#!/usr/bin/env python3
"""پیش‌نمایش خام قسمت ۱: ترکیب تصویر/کلیپ + صدا با FFmpeg (بدون موسیقی/افکت).
اجرا:  python3 tools/build_ep01_draft.py   → out/ep01_draft.mp4
نگاشت نما←فایل‌ها در TIMELINE است؛ با تغییر تصویرها فقط همین را عوض کن."""
import glob, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A, I, V, OUT = (os.path.join(ROOT, p) for p in ("assets/audio", "assets/images", "assets/video", "out"))
GAP = 0.25   # مکث بین خط‌ها (ثانیه)
TAIL = 0.5   # مکث پایان هر نما
# نما: (شمارهٔ فایل‌های صوتی، تصویر ثابت، کلیپ اختیاری)
TIMELINE = {
  "s01": ([1],        "02.png", None),
  "s02": ([2, 3, 4],  "04.png", "04.mp4"),
  "s03": ([5, 6, 7],  "03.png", None),
  "s04": ([8, 9, 10, 11], "05.png", "05.mp4"),
  "s05": ([12, 13, 14],   "06.png", "06.mp4"),
  "s06": ([15, 16],   "07.png", None),
}
W, H, FPS = 1280, 720, 24
def run(*a): subprocess.run(a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]).decode())
def audio_file(n):
    m = glob.glob(os.path.join(A, f"{n:02d}.*.mp3")); 
    if not m: sys.exit(f"فایل صوتی {n:02d} پیدا نشد")
    return m[0]
os.makedirs(OUT, exist_ok=True); parts=[]; report=[]
for sid,(auds,img,clip) in TIMELINE.items():
    files=[audio_file(n) for n in auds]
    lst=os.path.join(OUT,f"{sid}_a.txt"); sil=os.path.join(OUT,"sil.wav")
    run("ffmpeg","-y","-f","lavfi","-i","anullsrc=r=44100:cl=mono","-t",str(GAP),sil)
    with open(lst,"w") as f:
        for k,p in enumerate(files):
            f.write(f"file '{p}'\n")
            if k<len(files)-1: f.write(f"file '{sil}'\n")
    wav=os.path.join(OUT,f"{sid}.wav")
    run("ffmpeg","-y","-f","concat","-safe","0","-i",lst,"-ar","44100","-ac","1","-af",f"apad=pad_dur={TAIL}",wav)
    d=dur(wav); out=os.path.join(OUT,f"{sid}.mp4")
    sc=f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}"
    if clip:
        run("ffmpeg","-y","-i",os.path.join(V,clip),"-i",wav,"-filter_complex",
            f"[0:v]{sc},tpad=stop_mode=clone:stop_duration={d}[v]","-map","[v]","-map","1:a","-t",f"{d:.2f}",
            "-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p","-c:a","aac",out)
    else:
        n=int(d*FPS)
        run("ffmpeg","-y","-loop","1","-i",os.path.join(I,img),"-i",wav,"-filter_complex",
            f"[0:v]scale=2560:-1,zoompan=z='1+0.08*on/{n}':d={n}:s={W}x{H}:fps={FPS}[v]","-map","[v]","-map","1:a","-t",f"{d:.2f}",
            "-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p","-c:a","aac",out)
    parts.append(out); report.append((sid,round(d,1),"کلیپ" if clip else "تصویر+زوم"))
with open(os.path.join(OUT,"all.txt"),"w") as f:
    for p in parts: f.write(f"file '{p}'\n")
final=os.path.join(OUT,"ep01_draft.mp4")
run("ffmpeg","-y","-f","concat","-safe","0","-i",os.path.join(OUT,"all.txt"),"-c","copy",final)
print(json.dumps(report,ensure_ascii=False)); print("جمع:",round(dur(final),1),"ثانیه ->",final)
