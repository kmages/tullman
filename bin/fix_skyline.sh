#!/usr/bin/env bash
set -euo pipefail

# --- config ---
SRC="${1:-}"                                    # required: input image path
WEB_ROOT="/var/www/tullman/assets"              # Nginx-served assets
PUBLIC_HTML="$HOME/tullman/frontend/public.html"

if [[ -z "$SRC" || ! -f "$SRC" ]]; then
  echo "Usage: $0 /path/to/skyline.png"; exit 1
fi

# ImageMagick needed
if ! command -v convert >/dev/null 2>&1; then
  echo "ImageMagick not found. Install: sudo apt-get update && sudo apt-get install -y imagemagick"
  exit 1
fi

sudo mkdir -p "$WEB_ROOT"
WORKDIR="$(mktemp -d)"; trap 'rm -rf "$WORKDIR"' EXIT
cp -f "$SRC" "$WORKDIR/src.png"

# Build a pure white-on-transparent silhouette (no blur/halo), then trim
convert "$WORKDIR/src.png" \
  \( +clone -colorspace gray -threshold 93% -morphology Dilate Diamond:1 \) \
  -alpha off -compose copyopacity -composite \
  -fill white -colorize 100 \
  -trim +repage "$WORKDIR/skyline.png"

# Deploy to Nginx assets
sudo cp -f "$WORKDIR/skyline.png" "$WEB_ROOT/skyline.png"
sudo chown www-data:www-data "$WEB_ROOT/skyline.png"
sudo chmod 644 "$WEB_ROOT/skyline.png"

# Compute a content hash and update the homepage reference
HASH="$(md5sum "$WEB_ROOT/skyline.png" | cut -c1-8)"
export HASH
python3 - <<'PY'
import os, re
from pathlib import Path

pub = Path(os.path.expanduser("~/tullman/frontend/public.html"))
html = pub.read_text(encoding="utf-8")
h = os.environ["HASH"]

# Ensure a simple <img> skyline with cache-busting hash
html = re.sub(r'<div\s+class="skyline"[^>]*>[\s\S]*?</div>',
              f'<div class="skyline"><img src="/assets/skyline.png?v={h}" alt="Chicago skyline outline"></div>',
              html, count=1)

# Clean CSS: no blur/shadow
html = re.sub(r'\.skyline\s*img\s*\{[^}]*\}',
              '.skyline img{width:100%;max-height:140px;height:auto;display:block;object-fit:contain;background:transparent;filter:none!important;box-shadow:none!important}',
              html, flags=re.S)

pub.write_text(html, encoding="utf-8")
print("Updated public.html with skyline hash:", h)
PY

# Reload Nginx (no downtime)
sudo nginx -t && sudo systemctl reload nginx || true

# Verify over HTTPS
curl -sS -o /dev/null -w "asset:%{http_code} bytes:%{size_download}\n" \
  "https://tullman.ai/assets/skyline.png?v=$HASH" || true

echo "Done. Open https://tullman.ai/ (hard refresh / private window)."
