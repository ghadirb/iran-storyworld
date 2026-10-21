#!/usr/bin/env python3
"""پیش‌نمایش خام قسمت ۳ (پیش‌نویس تأییدنشده). خروجی: out/ep03_draft.mp4
بدون برش (پیش‌زمینهٔ کامل + پس‌زمینهٔ محو)، بدون موسیقی/افکت. ترتیب فایل‌ها را فقط از scenes.json قسمت ۳ می‌گیرد.
"""
import glob, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A, I, V = (os.path.join(ROOT, p) for p in ("assets/audio", "assets/images", "assets/video"))
OUT = os.path.join(ROOT, "out"); TMP = os.path.join(OUT, "ep03_tmp")
GAP, TAIL, W, H, FPS = 0.35, 0.5, 1280, 720, 24
# خطوط صوتی هر نما: شمارهٔ فایل یا پیشوند نام (برای فایل ۳۰ که اشتباهاً «20.بعضی‌ها» نام گرفته)
TIMELINE = {
  "s01": (["36.", "37."],             "14.png", "14.mp4"),
  "s02": (["38.", "39.", "40."],      "15.png", None),
  "s03": (["41.", "42.", "43."],      "16.png", "16.mp4"),
  "s04": (["44.", "45.", "46."],      "17.png", "17.mp4"),
  "s05": (["47.", "48.", "49."],      "18.png", None),
  "s06": (["50.", "51.", "52."],      "19.png", "19.mp4"),
}
ENC = ["-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p"]
def FIT(w, h): return (f"split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:6[bg];"
                       f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={FPS}")
def run(*a): subprocess.run(a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]).decode())
def audio(prefix):
    m = sorted(glob.glob(os.path.join(A, prefix + "*.mp3")))
    if len(m) != 1: sys.exit(f"فایل صوتی با پیشوند «{prefix}» یافت نشد یا یکتا نیست: {m}")
    return m[0]
os.makedirs(TMP, exist_ok=True); parts=[]; rep=[]
sil=os.path.join(TMP,"sil.wav"); run("ffmpeg","-y","-f","lavfi","-i","anullsrc=r=44100:cl=mono","-t",str(GAP),sil)
for sid,(auds,img,clip) in TIMELINE.items():
    lst=os.path.join(TMP,f"{sid}_a.txt")
    with open(lst,"w") as f:
        for k,p in enumerate(auds):
            f.write(f"file '{audio(p)}'\n")
            if k<len(auds)-1: f.write(f"file '{sil}'\n")
    wav=os.path.join(TMP,f"{sid}.wav"); run("ffmpeg","-y","-f","concat","-safe","0","-i",lst,"-ar","44100","-ac","1","-af",f"apad=pad_dur={TAIL}",wav)
    d=dur(wav); vid=os.path.join(TMP,f"{sid}_v.mp4"); n=int(d*FPS)+1
    if clip:
        cp=os.path.join(V,clip); cd=dur(cp); head=os.path.join(TMP,f"{sid}_head.mp4")
        run("ffmpeg","-y","-i",cp,"-filter_complex",f"[0:v]{FIT(W,H)}[v]","-map","[v]","-an",*ENC,head)
        if d>cd+0.05:
            # بعد از پایان کلیپ: آخرین فریم کامل (با پس‌زمینهٔ محو) با زوم بسیار ملایم
            last=os.path.join(TMP,f"{sid}_last.png"); rest=d-cd; m=int(rest*FPS)+1
            run("ffmpeg","-y","-sseof","-0.1","-i",cp,"-frames:v","1","-update","1",last)
            tail=os.path.join(TMP,f"{sid}_tail.mp4")
            run("ffmpeg","-y","-loop","1","-framerate",str(FPS),"-i",last,"-filter_complex",
                f"[0:v]{FIT(2*W,2*H)},zoompan=z='1+0.05*on/{m}':d={m}:s={W}x{H}:fps={FPS}[v]","-map","[v]","-t",f"{rest:.2f}",*ENC,tail)
            ll=os.path.join(TMP,f"{sid}_vl.txt"); open(ll,"w").write(f"file '{head}'\nfile '{tail}'\n")
            run("ffmpeg","-y","-f","concat","-safe","0","-i",ll,"-c","copy",vid)
        else: vid=head
    else:
        run("ffmpeg","-y","-loop","1","-framerate",str(FPS),"-i",os.path.join(I,img),"-filter_complex",
            f"[0:v]{FIT(2*W,2*H)},zoompan=z='1+0.06*on/{n}':d={n}:s={W}x{H}:fps={FPS}[v]","-map","[v]","-t",f"{d:.2f}",*ENC,vid)
    out=os.path.join(TMP,f"{sid}.mp4")
    run("ffmpeg","-y","-i",vid,"-i",wav,"-map","0:v","-map","1:a","-t",f"{d:.2f}","-c:v","copy","-c:a","aac","-b:a","192k",out)
    parts.append(out); rep.append((sid,round(d,1),"کلیپ" if clip else "تصویر+زوم"))
with open(os.path.join(TMP,"all.txt"),"w") as f:
    for p in parts: f.write(f"file '{p}'\n")
final=os.path.join(OUT,"ep03_draft.mp4")
run("ffmpeg","-y","-f","concat","-safe","0","-i",os.path.join(TMP,"all.txt"),"-c","copy",final)
print(rep); print("جمع:",round(dur(final),1),"ثانیه ->",final)
