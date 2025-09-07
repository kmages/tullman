#!/usr/bin/env bash
set -euo pipefail

CFILE="$HOME/tullman/app/composer.py"
STAMP=$(date +%Y%m%d-%H%M%S)

echo "[1/5] backup composer.py"
cp -f "$CFILE" "$CFILE.bak.$STAMP"

echo "[2/5] patch composer (Israel -> opinion mode, Howard-only links)"
python3 - <<'PY'
from pathlib import Path, re, json, sys
p = Path.home()/ "tullman" / "app" / "composer.py"
s = p.read_text(encoding="utf-8")

# --- helpers (idempotent) ---
if 'SAFE_HOWARD =' not in s:
    s += '''

SAFE_HOWARD = ("howardtullman.com","tullman.blogspot.com","blogspot.com","inc.com","northwestern.edu","wikipedia.org")

def _is_israel_prompt(q:str)->bool:
    q=(q or "").lower()
    keys=("israel","gaza","hamas","idf","west bank","antisemitism","two-state","two state","middle east")
    return any(k in q for k in keys)

def _howard_sources(topic:str, max_links:int=3)->list[dict]:
    """Return Howard-only links on the topic (clean titles; de-noise)."""
    out, seen = [], set()
    DATA = Path.home() / "tullman" / "data" / "content" / "content.jsonl"
    if not DATA.exists(): return out
    KEYW = ("israel","gaza","hamas","antisemitism","two-state","two state","middle east")
    EXCL = ("chunk","toady","roberts","putin","trump","election","politic")
    with DATA.open("r", encoding="utf-8") as f:
        for line in f:
            try: r = json.loads(line)
            except: continue
            u = (r.get("url") or "").strip()
            if not u: continue
            host = re.sub(r"^https?://","",u).split("/")[0].lower()
            if not any(host.endswith(d) for d in SAFE_HOWARD): continue
            title = (r.get("title") or r.get("source_name") or u).strip()
            text  = (r.get("text")  or "").strip()
            blob  = f"{title} {text}".lower()
            if not any(k in blob for k in KEYW): continue
            if any(x in title.lower() for x in EXCL): continue
            # clean title
            import re as _re
            title = _re.sub(r'\s*-\s*chunk\s*\d+\s*$','', title, flags=_re.I)
            title = _re.sub(r'\s*chunk\s*\d+\s*$','', title, flags=_re.I).strip()
            if title and title.upper()==title: title = title.title()
            key = u.lower()
            if key in seen: continue
            seen.add(key)
            out.append({"title": title or "Source", "url": u})
            if len(out) >= max_links: break
    return out
'''

# --- insert early-return into compose() (idempotent) ---
start = s.find('def compose(')
if start == -1:
    print("[ERR] compose() not found"); sys.exit(1)

# find end of def line to insert immediately after it
ln_end = s.find('\n', start)
head, tail = s[:ln_end+1], s[ln_end+1:]

if '# === israel opinion early return ===' not in tail:
    inject = (
        "    # === israel opinion early return ===\n"
        "    if _is_israel_prompt(prompt):\n"
        "        links = _howard_sources(prompt, max_links=2)\n"
        "        body = (\n"
        "            \"### Israel — my view\\n\"\n"
        "            \"**Position:** …\\n\"\n"
        "            \"**Why:** …\\n\"\n"
        "            \"**Red lines:** …\\n\"\n"
        "            \"**Progress looks like:** …\"\n"
        "        )\n"
        "        try:\n"
        "            md = _gpt_rewrite(prompt, body, prior, links)  # uses PRIOR\n"
        "        except Exception:\n"
        "            md = body\n"
        "        # no greeting; normalize phrasing\n"
        "        md = md.replace(\"Hi - I'm Howard\",\"\"\").replace(\"Hi — I’m Howard\",\"\"\").replace(\"founded or ran\",\"founded and ran\")\n"
        "        return md, links\n"
    )
    tail = inject + tail

s = head + tail
p.write_text(s, encoding='utf-8')
print("[patched] composer: israel opinion route + Howard-only links")
PY

echo "[3/5] import-check composer"
 /home/kmages/tullman/venv/bin/python3 - <<'PY'
import sys, importlib
sys.path.insert(0,"/home/kmages/tullman")
import app.composer as c
print("COMPOSER_IMPORT_OK")
PY

echo "[4/5] restart service"
sudo systemctl restart tullman

echo "[5/5] smoke test (Israel opinion)"
curl -sS -H 'Content-Type: application/json' \
  -d '{"prompt":"What are your views on Israel?","public":true}' \
  https://tullman.ai/chat | python3 -m json.tool || true
