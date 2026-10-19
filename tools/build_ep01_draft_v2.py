#!/usr/bin/env python3
"""نسخهٔ ۲ پیش‌نمایش قسمت ۱ — بدون برش تصویر.
کلیپ‌هایی که نسبتشان ۱۶:۹ نیست کامل در پیش‌زمینه می‌آیند و پشتشان نسخهٔ محوشدهٔ خودشان است.
خروجی: out/ep01_draft_v2.mp4 (نسخهٔ ۱ دست‌نخورده می‌ماند). صدا، ترتیب نماها و متن تغییری نکرده‌اند."""
import glob, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A, I, V = (os.path.join(ROOT, p) for p in ("assets/audio", "assets/images", "assets/video"))
OUT = os.path.join(ROOT, "out"); TMP = os.path.join(OUT, "v2_tmp")
GAP, TAIL = 0.35, 0.5
TIMELINE = {
  "s01": ([1],              "02.png", None),
  "s02": ([2, 3, 4],        "04.png", "04.mp4"),
  "s03": ([5, 6, 7],        "03.png", None),
  "s04": ([8, 9, 10, 11],   "05.png", "05.mp4"),
  "s05": ([12, 18, 13, 14], "06.png", "06.mp4"),
  "s06": ([17, 15, 16],     "07.png", "07.mp4"),
}
W, H, FPS = 1280, 720, 24
ENC = ["-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p"]
# پیش‌زمینهٔ کامل + پس‌زمینهٔ محو؛ اگر نسبت ۱۶:۹ باشد عملاً پس‌زمینه دیده نمی‌شود
FIT = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:6[bg];"
       f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={FPS}")
def run(*a): subprocess.run(a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]).decode())
def audio_file(n):
    m = glob.glob(os.path.join(A, f"{n:02d}.*.mp3"))
    if not m: sys.exit(f"فایل صوتی {n:02d} پیدا نشد")
    return m[0]
os.makedirs(TMP, exist_ok=True); parts=[]; report=[]
sil=os.path.join(TMP,"sil.wav"); run("ffmpeg","-y","-f","lavfi","-i","anullsrc=r=44100:cl=mono","-t",str(GAP),sil)
for sid,(auds,img,clip) in TIMELINE.items():
    lst=os.path.join(TMP,f"{sid}_a.txt")
    with open(lst,"w") as f:
        for k,n in enumerate(auds):
            f.write(f"file '{audio_file(n)}'\n")
            if k<len(auds)-1: f.write(f"file '{sil}'\n")
    wav=os.path.join(TMP,f"{sid}.wav")
    run("ffmpeg","-y","-f","concat","-safe","0","-i",lst,"-ar","44100","-ac","1","-af",f"apad=pad_dur={TAIL}",wav)
    d=dur(wav); vid=os.path.join(TMP,f"{sid}_v.mp4"); out=os.path.join(TMP,f"{sid}.mp4")
    if clip:
        cp=os.path.join(V,clip); cd=dur(cp)
        head=os.path.join(TMP,f"{sid}_head.mp4")
        run("ffmpeg","-y","-i",cp,"-filter_complex",f"[0:v]{FIT}[v]","-map","[v]","-an",*ENC,head)
        if d>cd+0.05:
            last=os.path.join(TMP,f"{sid}_last.png"); rest=d-cd
            run("ffmpeg","-y","-sseof","-0.1","-i",cp,"-frames:v","1","-update","1",last)
            tail=os.path.join(TMP,f"{sid}_tail.mp4")
            run("ffmpeg","-y","-loop","1","-framerate",str(FPS),"-i",last,"-filter_complex",f"[0:v]{FIT}[v]","-map","[v]","-t",f"{rest:.2f}",*ENC,tail)
            ll=os.path.join(TMP,f"{sid}_vl.txt"); open(ll,"w").write(f"file '{head}'\nfile '{tail}'\n")
            run("ffmpeg","-y","-f","concat","-safe","0","-i",ll,"-c","copy",vid)
        else: vid=head
    else:
        n=int(d*FPS)  # تصویرهای ثابت ۱۶:۹اند (۱۶۷۲×۹۴۱)؛ فقط زوم بسیار ملایم
        run("ffmpeg","-y","-loop","1","-i",os.path.join(I,img),"-filter_complex",
            f"[0:v]scale=2560:1440:force_original_aspect_ratio=increase,crop=2560:1440,zoompan=z='1+0.06*on/{n}':d={n}:s={W}x{H}:fps={FPS},setsar=1[v]",
            "-map","[v]","-t",f"{d:.2f}",*ENC,vid)
    run("ffmpeg","-y","-i",vid,"-i",wav,"-map","0:v","-map","1:a","-t",f"{d:.2f}","-c:v","copy","-c:a","aac","-b:a","192k",out)
    parts.append(out); report.append((sid,round(d,1),"کلیپ" if clip else "تصویر+زوم"))
with open(os.path.join(TMP,"all.txt"),"w") as f:
    for p in parts: f.write(f"file '{p}'\n")
final=os.path.join(OUT,"ep01_draft_v2.mp4")
run("ffmpeg","-y","-f","concat","-safe","0","-i",os.path.join(TMP,"all.txt"),"-c","copy",final)
print(json.dumps(report,ensure_ascii=False)); print("جمع:",round(dur(final),1),"ثانیه ->",final)
