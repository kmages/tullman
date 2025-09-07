#!/usr/bin/env bash
set -euo pipefail
URL="https://tullman.ai/chat"
HDR='Content-Type: application/json'
PY="/home/kmages/tullman/venv/bin/python3"

CYN=$'\033[1;36m'; GRN=$'\033[1;32m'; YLW=$'\033[1;33m'; NC=$'\033[0m'

sid=""

make_body () {
  "$PY" -c 'import sys,json; q=sys.argv[1]; sid=sys.argv[2]; p={"prompt":q,"public":True};
if sid: p["session_id"]=sid; print(json.dumps(p))' "$1" "${sid:-}"
}

show_body () {
  # Try JSON first; if it fails, print raw
  "$PY" -c '
import sys, json
raw = sys.stdin.read()
try:
    d = json.loads(raw)
    sid = d.get("session_id") or ""
    ans = (d.get("answer") or "").strip()
    src = d.get("sources") or []
    print(ans)
    if src:
        print("\n-- Links --")
        for s in src:
            t=(s.get("title") or s.get("url") or "").strip()
            u=(s.get("url") or "").strip()
            if u: print("- {}  <{}>".format(t,u))
    print("\n__SID__ {}".format(sid))
except Exception:
    # Not JSON: show the raw body so we see what actually came back
    print("---- Raw body ----")
    print(raw.strip())
'
}

ask () {
  local Q="$1"
  local BODY=$(make_body "$Q")
  local TMPB=$(mktemp) TMPH=$(mktemp)

  local CODE=$(curl -sS -o "$TMPB" -D "$TMPH" -w '%{http_code}' -H "$HDR" -d "$BODY" "$URL" || echo "curl_err")
  local TYPE=$(grep -i '^content-type:' "$TMPH" | tr -d '\r' | awk '{print tolower($0)}' | sed 's/content-type: *//')
  local BYTES=$(wc -c < "$TMPB" | tr -d ' ')

  echo -e "${CYN}=== You ===${NC} $Q"
  echo "HTTP: $CODE | type: ${TYPE:-unknown} | bytes: $BYTES"

  if [[ "$BYTES" -gt 0 ]]; then
    show_body < "$TMPB"
    # capture sid if JSON
    newsid=$("$PY" -c 'import sys,json; import os
raw=sys.stdin.read()
try:
    print((json.loads(raw).get("session_id") or ""))
except Exception:
    print("")' < "$TMPB")
    [[ -n "$newsid" ]] && sid="$newsid"
  else
    echo "---- Empty body ----"
  fi

  rm -f "$TMPB" "$TMPH"
  echo
}

echo -e "${GRN}# tullman.ai smoke${NC}"
ask "Who is Howard Tullman?"
ask "What changed at Kendall under your leadership?"
ask "What's something people forget when chasing goals?"
ask "Why do I need an AI strategy?"
echo -e "${YLW}(done)${NC}"
