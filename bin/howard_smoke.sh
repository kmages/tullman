#!/usr/bin/env bash
set -euo pipefail

URL="https://tullman.ai/chat"
HDR='Content-Type: application/json'
PY="/home/kmages/tullman/venv/bin/python3"
SID=""
TS=$(date +%Y%m%d-%H%M%S)
OUT="$HOME/howard_smoke_${TS}.log"

CYN=$'\033[1;36m'; GRN=$'\033[1;32m'; YLW=$'\033[1;33m'; RED=$'\033[1;31m'; DIM=$'\033[2m'; NC=$'\033[0m'

make_body () {
  "$PY" - "$1" "$2" <<'PY'
import sys, json
q   = sys.argv[1]
sid = sys.argv[2]
payload = {"prompt": q, "public": True}
if sid:
    payload["session_id"] = sid
print(json.dumps(payload))
PY
}

pretty_json () {
  "$PY" - <<'PY'
import sys, json
data = json.load(sys.stdin)
sid  = data.get("session_id") or ""
ans  = (data.get("answer") or "").strip()
srcs = data.get("sources") or []
print(ans)
if srcs:
    print("\n-- Links --")
    for s in srcs:
        t = (s.get("title") or s.get("url") or "").strip()
        u = (s.get("url") or "").strip()
        if u: print(f"- {t}  <{u}>")
print(f"\n__SID__ {sid}")
PY
}

call () {
  local Q="$1" SID_IN="${2:-}"
  local BODY TMP=/tmp/chat.$$ BODYHDR=/tmp/chat.$$.hdr CODE TYPE SID_OUT

  echo -e "${CYN}=== You ===${NC} $Q" | tee -a "$OUT"

  BODY=$(make_body "$Q" "$SID_IN")
  CODE=$(curl -sS -o "$TMP" -D "$BODYHDR" -w '%{http_code}' -H "$HDR" -d "$BODY" "$URL" || echo "curl_err")
  TYPE=$(grep -i '^content-type:' "$BODYHDR" | tr -d '\r' | awk '{print tolower($0)}' | sed 's/content-type: *//')

  echo "HTTP: $CODE | type: ${TYPE:-unknown}" | tee -a "$OUT"

  if [ "$CODE" = "200" ] && echo "${TYPE:-}" | grep -q 'application/json'; then
    # valid JSON → pretty print and capture SID
    SID_OUT=$(pretty_json < "$TMP" | tee -a "$OUT" | awk '/^__SID__/ {print $2}')
    [ -n "$SID_OUT" ] && SID="$SID_OUT"
  else
    echo -e "${RED}---- Non-JSON response (showing first 400 bytes) ----${NC}" | tee -a "$OUT"
    head -c 400 "$TMP" | sed -e 's/\x1b\[[0-9;]*m//g' | tee -a "$OUT"
    echo -e "\n__SID__" | tee -a "$OUT"
  fi

  rm -f "$TMP" "$BODYHDR"
  echo | tee -a "$OUT"   # spacer
}

echo "# Howard smoke @ $TS" | tee "$OUT"

# One session for first two, then fresh for others
call "Who is Howard Tullman?" ""
call "Why do I need an AI strategy?" ""
call "What did you change at Kendall College during the turnaround?" ""
call "What's something people forget when chasing goals?" ""
call "How do you define success?" ""

echo -e "${DIM}(log saved to $OUT)${NC}"
