#!/usr/bin/env bash
# ساخت افزایشی همهٔ قسمت‌های tools/build_map.txt: قسمتی که ورودی‌اش تغییر نکرده از build-cache برداشته می‌شود.
# متغیرها: REBUILD_ALL=true (نادیده‌گرفتن کش)، ENC_TAG (تغییر پارامترهای انکودینگ)، BUILD_MAP (پیش‌فرض tools/build_map.txt)
set -euo pipefail
cd "$(dirname "$0")/.."
MAP="${BUILD_MAP:-tools/build_map.txt}"
mkdir -p out build build-cache
: > build/manifest.txt
while read -r id script outfile; do
  h=$(python3 tools/episode_hash.py "tools/$script")
  cached="build-cache/$id.$h.mp4"
  if [ -s "$cached" ] && [ "${REBUILD_ALL:-false}" != "true" ]; then
    echo "== $id: از کش ($h)"
  else
    echo "== $id: ساخت ($h)"
    python3 "tools/$script" < /dev/null
    ffmpeg -nostdin -y -loglevel error -i "$outfile" -c:v libx264 -crf 26 -preset medium -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "build-cache/tmp_$id.mp4"
    find build-cache -name "$id.*.mp4" ! -name "$id.$h.mp4" -delete
    mv "build-cache/tmp_$id.mp4" "$cached"
    [ -n "${GITHUB_ENV:-}" ] && echo "BUILT_NEW=1" >> "$GITHUB_ENV" || true
  fi
  cp "$cached" "build/$id.mp4"
  ffmpeg -nostdin -y -loglevel error -ss 6 -i "build/$id.mp4" -frames:v 1 -vf scale=640:-2 -q:v 4 "build/$id.jpg"
  echo "videos/$id.mp4 build/$id.mp4 video/mp4" >> build/manifest.txt
  echo "posters/$id.jpg build/$id.jpg image/jpeg" >> build/manifest.txt
done < <(grep -v '^\s*#' "$MAP" | grep -v '^\s*$')
# کاتالوگ آخر می‌آید تا قسمت فقط بعد از آماده‌شدن فایل‌هایش دیده شود
echo "catalog.json catalog/catalog.json application/json" >> build/manifest.txt
ls -la build
