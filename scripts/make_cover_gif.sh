#!/usr/bin/env bash
# Genera docs/img/cover_en.gif y cover_es.gif (Resumen → Mapa → Corredor) con capturas reales del sitio.
# Requiere google-chrome y ffmpeg, y site/data/ generado (python -m scripts.export_public).
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=8770; TMP="$(mktemp -d)"
python3 -m http.server -d site "$PORT" >/dev/null 2>&1 & SRV=$!
trap 'kill $SRV 2>/dev/null; rm -rf "$TMP"' EXIT
sleep 1
for lang in en es; do
  i=0
  for tab in overview map corridor; do
    i=$((i+1))
    google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
      --user-data-dir="$TMP/chrome" --virtual-time-budget=6000 --window-size=1280,720 \
      --screenshot="$TMP/$lang$i.png" "http://localhost:$PORT/?tab=$tab&lang=$lang" >/dev/null 2>&1
  done
  ffmpeg -y -loglevel error -loop 1 -t 3 -i "$TMP/${lang}1.png" -loop 1 -t 3 -i "$TMP/${lang}2.png" -loop 1 -t 3 -i "$TMP/${lang}3.png" \
    -filter_complex "[0][1]xfade=transition=fade:duration=0.5:offset=2.5[a];[a][2]xfade=transition=fade:duration=0.5:offset=5[b];[b]fps=12,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4" \
    -loop 0 "docs/img/cover_$lang.gif"
done
ls -l docs/img/cover_*.gif
