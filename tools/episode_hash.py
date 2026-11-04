#!/usr/bin/env python3
"""اثرانگشت ورودی‌های یک قسمت (برای بیلد افزایشی). استفاده: python3 tools/episode_hash.py tools/<script>.py
اگر اسکریپت، ورودی‌هایی (صدا/تصویر/کلیپ) نداشته باشد یا قدیمی باشد، فقط خود اسکریپت و فایل‌های مشترک حساب می‌شود.
اثرانگشت = اسکریپت + فایل‌های صوتی/تصویری/کلیپ ارجاع‌داده‌شده در TIMELINE + فایل‌های صوتی غیرعددی (مثل موسیقی) + برچسب ENC_TAG."""
import hashlib, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = open(sys.argv[1], "rb").read(); text = raw.decode("utf8", "replace")
tokens = {str(int(x)) for x in re.findall(r'["\'](\d{1,4})[._]?["\']', text)}
legacy = "TIMELINE" not in text
h = hashlib.sha256(); h.update(os.environ.get("ENC_TAG", "v1").encode()); h.update(raw)
for d in ("audio", "images", "video"):
    base = os.path.join(ROOT, "assets", d)
    if not os.path.isdir(base): continue
    for name in sorted(os.listdir(base)):
        p = os.path.join(base, name)
        if not os.path.isfile(p) or name.endswith((".md", ".txt", ".gitkeep")): continue
        m = re.match(r"(\d+)", name)
        if m:
            n = str(int(m.group(1)))
            take = (n in tokens) or (legacy and int(n) < 100)
        else:
            take = (d == "audio")   # فایل‌های مشترک مثل موسیقی
        if take:
            h.update(os.path.join(d, name).encode()); h.update(open(p, "rb").read())
print(h.hexdigest()[:16])
