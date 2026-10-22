#!/usr/bin/env python3
"""نسخهٔ موسیقی‌دار پیش‌نمایش قسمت ۵ (پیشنهادی، تأییدنشده). خروجی: out/ep05_draft_music.mp4
اول tools/build_ep05_draft.py را اجرا می‌کند (نسخهٔ خام دست‌نخورده می‌ماند) و فقط صدا را با لایه‌های موجود مخلوط می‌کند:
موسیقی بی‌کلام (کم‌حجم، با کاهش خودکار زیر گفتار)، محیط کارگاه (خیلی کم)، و صدای چکش فقط در نمای ۱ (کارگاه).
فایل صوتی جدیدی ساخته یا جعل نمی‌شود."""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out"); TMP = os.path.join(OUT, "ep05_tmp"); A = os.path.join(ROOT, "assets/audio")
def run(*a): subprocess.run(a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]).decode())
raw = os.path.join(OUT, "ep05_draft.mp4")
if not os.path.isfile(raw): subprocess.run([sys.executable, os.path.join(ROOT, "tools/build_ep05_draft.py")], check=True)
ds = [dur(os.path.join(TMP, f"s0{i}.mp4")) for i in range(1, 7)]
total = dur(raw); s2 = 0.0; s2_len = ds[0]
music, amb, ham = (os.path.join(A, n) for n in ("موسیقی بی‌کلام.wav", "محیط کارگاه.wav", "صدای چکش.wav"))
for p in (music, amb, ham):
    if not os.path.isfile(p): sys.exit(f"فایل لازم نیست/نیست: {p}")
h_delay = int((s2 + 0.4) * 1000); h_len = max(1.0, s2_len - 1.5)
out = os.path.join(OUT, "ep05_draft_music.mp4"); fo = max(0, total - 2.5)
mix = (
 # موسیقی: دو نسخه با کراس‌فید برای حلقهٔ بدون پرش، سپس فید ورود/خروج
 "[1:a]volume=0.15[m1];[2:a]volume=0.15[m2];[m1][m2]acrossfade=d=2,"
 f"afade=t=in:st=0:d=1.5,afade=t=out:st={fo:.2f}:d=2.5[music0];"
 "[music0][0:a]sidechaincompress=threshold=0.025:ratio=6:attack=25:release=400[music];"
 f"[3:a]volume=0.06,aloop=loop=-1:size=2e9,atrim=0:{total:.2f},afade=t=in:st=0:d=1.5,afade=t=out:st={fo:.2f}:d=2.5[amb];"
 f"[4:a]atrim=0:{h_len:.2f},afade=t=in:st=0:d=0.4,afade=t=out:st={h_len-0.6:.2f}:d=0.6,volume=0.10,adelay={h_delay}|{h_delay}[ham];"
 "[0:a][music][amb][ham]amix=inputs=4:duration=first:dropout_transition=2:normalize=0,"
 "loudnorm=I=-18:TP=-1.5:LRA=11,alimiter=limit=0.95[a]")
run("ffmpeg","-y","-i",raw,"-i",music,"-i",music,"-i",amb,"-i",ham,"-filter_complex",mix,
    "-map","0:v:0","-map","[a]","-t",f"{total:.3f}","-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart",out)
rep = {"episode":"ch01-ep05","status":"preview-music","output":"ep05_draft_music.mp4","duration_seconds":round(dur(out),2),
       "scene_seconds":[round(d,1) for d in ds],"hammer":{"at_seconds":round(s2+0.4,1),"length":round(h_len,1)},
       "limitations":["تماشای انسانی لازم است","افکت اختصاصی قدم، باد، طناب و ارابه موجود نیست و جعل نشده"]}
json.dump(rep, open(os.path.join(OUT,"ep05_draft_music_report.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(rep, ensure_ascii=False)); print(out)
