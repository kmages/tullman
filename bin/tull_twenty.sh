#!/usr/bin/env bash
set -euo pipefail
URL="https://tullman.ai/chat"
HDR='Content-Type: application/json'
PY="/home/kmages/tullman/venv/bin/python3"
TS=$(date +%Y%m%d-%H%M%S)
OUT="$HOME/twenty_run_${TS}.log"

mapfile -t Qs <<'EOF'
Who is Howard Tullman?
What changed at Kendall under your leadership?
Why do I need an AI strategy?
Explain relativity to a ten year old.
What’s your boldest opinion?
How do you define success?
Why is kindness underrated?
Why do people fear death?
What advice would you give your younger self?
Does true love exist, or is it just chemistry?
Tell me about your most irrational belief.
What’s one thing people misunderstand about you?
What’s your theory of free will?
How do you stay grounded?
What’s your secret fuel?
What’s your most unshakable belief?
What’s your core trait?
What’s the cost of being misunderstood?
What do people need to hear more often?
What’s something people forget when chasing goals?
EOF

make_body () { "$PY" - <<'PY' "$1"
import sys,json; print(json.dumps({"prompt": sys.argv[1], "public": True}, separators=(",",":")))
PY
}

show_file () { "$PY" - <<'PY' "$1"
import sys,json,gzip
p=sys.argv[1]; raw=open(p,'rb').read()
try: txt=raw.decode('utf-8')
except UnicodeDecodeError:
    try: txt=gzip.decompress(raw).decode('utf-8')
    except Exception: txt=''
if not txt: print("---- Raw body (binary) ----"); print(raw[:160]); sys.exit(0)
try:
    d=json.loads(txt)
    ans=(d.get("answer") or "").strip()
    src=d.get("sources") or []
    print(ans)
    if src:
        print("\n-- Links --")
        for s in src:
            if s.get("url"): print(f"- {(s.get('title') or s['url']).strip()}  <{s['url'].strip()}>")
except Exception: print(txt.strip())
PY
}

echo "# twenty questions @ $TS" | tee "$OUT"
for Q in "${Qs[@]}"; do
  echo -e "\n=== You === $Q" | tee -a "$OUT"
  TMPB=$(mktemp) TMPH=$(mktemp)
  CODE=$(curl -sS --compressed -o "$TMPB" -D "$TMPH" -w '%{http_code}' -H "$HDR" -d "$(make_body "$Q")" "$URL" || echo curl_err)
  TYPE=$(grep -i '^content-type:' "$TMPH" | tr -d '\r' | sed 's/.*: *//I')
  BYTES=$(wc -c < "$TMPB" | tr -d ' ')
  echo "HTTP: $CODE | type: ${TYPE:-unknown} | bytes: $BYTES" | tee -a "$OUT"
  if [[ "$BYTES" -gt 0 ]]; then show_file "$TMPB" | tee -a "$OUT"; else echo "---- Empty body ----" | tee -a "$OUT"; fi
  rm -f "$TMPB" "$TMPH"
done
echo -e "\n# log: $OUT"
