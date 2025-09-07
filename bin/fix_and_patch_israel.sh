#!/usr/bin/env bash
set -euo pipefail
CFILE="$HOME/tullman/app/composer.py"
STAMP=$(date +%Y%m%d-%H%M%S)

echo "[1/4] backup composer.py"
cp -f "$CFILE" "$CFILE.bak.$STAMP"

echo "[2/4] sanitize bad imports & add Israel opinion route"
python3 - <<'PY'
from pathlib import Path, re, sys, json
p = Path.home()/ "tullman" / "app" / "composer.py"
s = p.read_text(encoding='utf-8')

# ---- sanitize bad imports like "from pathlib import Path, re, json" ----
def split_path_import(m):
    names = [x.strip() for x in m.group(1).split(',')]
    keep_path = 'Path' in names
    extras = [n for n in names if n and n!='Path']
    out = 'from pathlib import Path' if keep_path else ''
    if extras:
        out += ('\n' if out else '') + 'import ' + ', '.join(extras)
    return out

s = re.sub(r'^\s*from\s+pathlib\s+import\s+([A-Za-z0-9_,\s]+)\s*$', split_path_import, s, flags=re.M)
s = re.sub(r'^\s*from\s+pathlib\s+import\s+json\s*$', 'import json', s, flags=re.M)
s = re.sub(r'^\s*from\s+pathlib\s+import\s+re\s*$',   'import re',   s, flags=re.M)
s = re.sub(r'^\s*from\s+pathlib\s+import\s+sys\s*$',  'import sys',  s, flags=re.M)

# ensure we have import re/json if we used them
if 'import re'   not in s: s = 'import re\n'   + s
if 'import json' not in s: s = 'import json\n' + s

# ---- helpers for Israel opinion route (idempotent) ----
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
            title = _re.sub(r'\\s*-\\s*chunk\\s*\\d+\\s*$','', title, flags=_re.I)
            title = _re.sub(r'\\s*chunk\\s*\\d+\\s*$','', title, flags=_re.I).strip()
            if title and title.upper()==title: title = title.title()
            key = u.lower()
            if key in seen: continue
            seen.add(key)
            out.append({"title": title or "Source", "url": u})
            if len(out) >= max_links: break
    return out
'''

# early-return in compose()
start = s.find('def compose(')
if start == -1:
    print("[ERR] compose() not found"); sys.exit(1)
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
        "            md = _gpt_rewrite(prompt, body, prior, links)\n"
        "        except Exception:\n"
        "            md = body\n"
        "        md = md.replace(\"Hi - I'm Howard\",\"\"\").replace(\"Hi — I’m Howard\",\"\"\").replace(\"founded or ran\",\"founded and ran\")\n"
        "        return md, links\n"
    )
    tail = inject + tail

p.write_text(head + tail, encoding='utf-8')
print("[patched] imports sanitized + israel route added")
PY

echo "[3/4] import-check composer"
 /home/kmages/tullman/venv/bin/python3 - <<'PY'
import sys, importlib
sys.path.insert(0,"/home/kmages/tullman")
import app.composer as c
print("COMPOSER_IMPORT_OK")
PY

echo "[4/4] restart + test"
sudo systemctl restart tullman
curl -sS -H 'Content-Type: application/json' \
  -d '{"prompt":"What are your views on Israel?","public":true}' \
  https://tullman.ai/chat | python3 -m json.tool || true
