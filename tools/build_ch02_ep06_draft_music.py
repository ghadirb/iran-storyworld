#!/usr/bin/env python3
"""پیش‌نمایش موسیقی‌دار فصل ۲ بخش ۶ «آبی دو جور» (تأییدنشده). خروجی: out/ch02_ep06_draft_music.mp4
برای هر نما: اگر assets/video/<شمارهٔ تصویر>.mp4 باشد از همان کلیپ (در صورت کوتاه‌تر بودن، تا ۱٫۶ برابر آهسته + زوم نرم؛ بدون برگشت به عقب) استفاده می‌شود، وگرنه تصویر ثابت با زوم بسیار ملایم.
صدا: فقط فایل‌های روایت/دیالوگ ۱۹۶ تا ۲۱۵ + موسیقی بی‌کلام (کم‌حجم، با کاهش خودکار زیر گفتار). افکت یا صدای تازه جعل نمی‌شود."""
import glob, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A, I, V = (os.path.join(ROOT, p) for p in ("assets/audio", "assets/images", "assets/video"))
OUT = os.path.join(ROOT, "out"); TMP = os.path.join(OUT, "ch02_ep06_tmp")
GAP, TAIL, W, H, FPS = 0.35, 0.6, 1280, 720, 24
TIMELINE = {  # نما: (خطوط صوتی، تصویر)
  "s01": (["196.", "197."], "73"), "s02": (["198.", "199.", "200."], "74"), "s03": (["201.", "202.", "203."], "75"),
  "s04": (["204."], "76"), "s05": (["205.", "206.", "207."], "77"), "s06": (["208.", "209.", "210."], "78"),
  "s07": (["211.", "212.", "213."], "79"), "s08": (["214.", "215."], "80"),
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
os.makedirs(TMP, exist_ok=True); parts = []; rep = []
sil = os.path.join(TMP, "sil.wav"); run("ffmpeg","-y","-f","lavfi","-i","anullsrc=r=44100:cl=mono","-t",str(GAP),sil)
for sid, (auds, num) in TIMELINE.items():
    lst = os.path.join(TMP, f"{sid}_a.txt")
    with open(lst, "w") as f:
        for k, p in enumerate(auds):
            f.write(f"file '{audio(p)}'\n")
            if k < len(auds)-1: f.write(f"file '{sil}'\n")
    wav = os.path.join(TMP, f"{sid}.wav"); run("ffmpeg","-y","-f","concat","-safe","0","-i",lst,"-ar","44100","-ac","1","-af",f"apad=pad_dur={TAIL}",wav)
    d = dur(wav); n = int(d*FPS)+1; vid = os.path.join(TMP, f"{sid}_v.mp4")
    clip = os.path.join(V, f"{num}.mp4"); img = os.path.join(I, f"{num}.png")
    if os.path.isfile(clip):
        # کلیپ فقط رو به جلو پخش می‌شود: تا ۱٫۶ برابر آهسته‌تر (با درون‌یابی فریم) و بعد زوم بسیار نرم از آخرین فریم؛ بدون رفت‌وبرگشت
        cd = dur(clip); f = min(1.6, d/cd) if d > cd else 1.0
        head = os.path.join(TMP, f"{sid}_head.mp4")
        slow = f",setpts={f:.4f}*PTS,minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1" if f > 1.01 else ""
        run("ffmpeg","-y","-i",clip,"-filter_complex",f"[0:v]{FIT(W,H)}{slow}[v]","-map","[v]","-an",*ENC,head)
        hd = dur(head); rest = d - hd
        if rest > 0.1:
            last = os.path.join(TMP, f"{sid}_last.png"); m = int(rest*FPS)+1
            run("ffmpeg","-y","-sseof","-0.1","-i",head,"-frames:v","1","-update","1",last)
            tail = os.path.join(TMP, f"{sid}_tail.mp4")
            run("ffmpeg","-y","-loop","1","-framerate",str(FPS),"-i",last,"-filter_complex",
                f"[0:v]scale={2*W}:{2*H},zoompan=z='1+0.06*pow(on/{m},1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={m}:s={W}x{H}:fps={FPS}[v]","-map","[v]","-t",f"{rest:.2f}",*ENC,tail)
            ll = os.path.join(TMP, f"{sid}_vl.txt"); open(ll,"w").write(f"file '{head}'\nfile '{tail}'\n")
            vid = os.path.join(TMP, f"{sid}_loop.mp4"); run("ffmpeg","-y","-f","concat","-safe","0","-i",ll,"-c","copy",vid)
        else: vid = head
        kind = f"کلیپ (آهسته×{f:.2f} + زوم نرم)"
    else:
        run("ffmpeg","-y","-loop","1","-framerate",str(FPS),"-i",img,"-filter_complex",
            f"[0:v]{FIT(2*W,2*H)},zoompan=z='1+0.06*on/{n}':d={n}:s={W}x{H}:fps={FPS}[v]","-map","[v]","-t",f"{d:.2f}",*ENC,vid)
        kind = "تصویر+زوم"
    o = os.path.join(TMP, f"{sid}.mp4")
    vcodec = ["-vf",f"fade=t=out:st={max(d-1.5,0):.2f}:d=1.5",*ENC] if sid == list(TIMELINE)[-1] else ["-c:v","copy"]  # نمای آخر با محوشدن به سیاه تمام می‌شود
    run("ffmpeg","-y","-i",vid,"-i",wav,"-map","0:v","-map","1:a","-t",f"{d:.2f}",*vcodec,"-c:a","aac","-b:a","192k",o)
    parts.append(o); rep.append((sid, round(d,1), kind))
with open(os.path.join(TMP, "all.txt"), "w") as f:
    for p in parts: f.write(f"file '{p}'\n")
raw = os.path.join(OUT, "ch02_ep06_draft.mp4")
run("ffmpeg","-y","-f","concat","-safe","0","-i",os.path.join(TMP,"all.txt"),"-c","copy",raw)
total = dur(raw); fo = max(0, total-2.5); music = os.path.join(A, "موسیقی بی‌کلام.wav")
if not os.path.isfile(music): sys.exit(f"فایل لازم نیست/نیست: {music}")
out = os.path.join(OUT, "ch02_ep06_draft_music.mp4")
mix = ("[1:a]volume=0.15[m1];[2:a]volume=0.15[m2];[m1][m2]acrossfade=d=2,"
       f"afade=t=in:st=0:d=1.5,afade=t=out:st={fo:.2f}:d=2.5[music0];"
       "[music0][0:a]sidechaincompress=threshold=0.025:ratio=6:attack=25:release=400[music];"
       "[0:a][music]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,"
       "loudnorm=I=-18:TP=-1.5:LRA=11,alimiter=limit=0.95[a]")
run("ffmpeg","-y","-i",raw,"-i",music,"-i",music,"-filter_complex",mix,"-map","0:v:0","-map","[a]","-t",f"{total:.3f}",
    "-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart",out)
r = {"episode":"ch02-ep06","status":"preview-music","output":"ch02_ep06_draft_music.mp4","duration_seconds":round(dur(out),2),
     "scenes":[{"id":a,"seconds":b,"source":c} for a,b,c in rep],
     "limitations":["تماشای انسانی لازم است","افکت اختصاصی (زنگوله، قدم شتر، باد) موجود نیست و جعل نشده"]}
json.dump(r, open(os.path.join(OUT,"ch02_ep06_draft_music_report.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(r, ensure_ascii=False)); print(out)
