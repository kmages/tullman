#!/usr/bin/env bash
set -euo pipefail

URL="https://tullman.ai/chat"
HDR='Content-Type: application/json'
PY="/home/kmages/tullman/venv/bin/python3"
TS=$(date +%Y%m%d-%H%M%S)
OUT="$HOME/twenty_run_${TS}.log"

# The 20 prompts (ASCII quotes only)
mapfile -t Qs <<'EOF'
What scares you most about AI?
What do you believe about the afterlife?
Why is kindness underrated?
What's your boldest opinion?
How do you define success?
Why do people fear death?
What advice would you give your younger self?
Does true love exist, or is it just chemistry?
Tell me about your most irrational belief.
What's one thing people misunderstand about you?
What's your theory of free will?
What scares you most about AI?
How do you stay grounded?
What's your secret fuel?
What's your most unshakable belief?
What's your core trait?
What's the cost of being misunderstood?
What do you believe people need to hear more often?
What's your relationship to solitude?
What's something people forget when chasing goals?
EOF

make_body () {
  local Q="$1"
  "$PY" -c 'import sys,json; q=sys.argv[1]; print(json.dumps({"prompt":q,"public":True}))' "$Q"
}

print_json () {
  "$PY" -c '
import sys,json
d=json.load(sys.stdin)
sid=d.get("session_id") or ""
ans=(d.get("answer") or "").strip()
src=d.get("sources") or []
print(ans)
if src:
  print("\n-- Links --")
  for s in src:
    t=(s.get("title") or s.get("url") or "").strip()
    u=(s.get("url") or "").strip()
    if u: print("- {}  <{}>".format(t,u))
print("\n__SID__ {}".format(sid))
'
}

echo "# twenty questions @ $TS" | tee "$OUT"
for Q in "${Qs[@]}"; do
  echo -e "\n=== You === $Q" | tee -a "$OUT"
  TMPB=$(mktemp); TMPH=$(mktemp)
  CODE=$(curl -sS -o "$TMPB" -D "$TMPH" -w '%{http_code}' -H "$HDR" -d "$(make_body "$Q")" "$URL" || echo "curl_err")
  TYPE=$(grep -i '^content-type:' "$TMPH" | tr -d '\r' | awk '{print tolower($0)}' | sed 's/content-type: *//')
  BYTES=$(wc -c < "$TMPB" | tr -d " ")
  echo "HTTP: $CODE | type: ${TYPE:-unknown} | bytes: $BYTES" | tee -a "$OUT"

  if [[ "$CODE" == "200" ]] && echo "${TYPE:-}" | grep -q 'application/json' && [[ "$BYTES" -gt 0 ]]; then
    print_json < "$TMPB" | tee -a "$OUT"
  else
    echo "---- Raw body (first 400B) ----" | tee -a "$OUT"
    head -c 400 "$TMPB" | tee -a "$OUT"; echo | tee -a "$OUT"
  fi
  rm -f "$TMPB" "$TMPH"
done

echo -e "\n# log: $OUT"
