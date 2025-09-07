#!/usr/bin/env bash
set -euo pipefail
PY="/home/kmages/tullman/venv/bin/python3"

CYN=$'\033[1;36m'; YLW=$'\033[1;33m'; NC=$'\033[0m'

hdr(){ echo; echo "${CYN}## $*${NC}"; }

hdr "DNS"
echo -n "A tullman.ai: " && dig +short A tullman.ai | tr '\n' ' ' && echo

hdr "Services"
echo -n "nginx: "    && sudo systemctl is-active nginx || true
echo -n "tullman: "  && sudo systemctl is-active tullman || true

hdr "Listeners (443/8080)"
ss -ltnp | egrep ':443|:8080' || true

hdr "TLS probe (CN + dates)"
echo | openssl s_client -servername tullman.ai -connect tullman.ai:443 2>/dev/null \
 | openssl x509 -noout -subject -dates | sed 's/^/  /'

hdr "Health (via nginx)"
curl -sS --max-time 4 https://tullman.ai/health | $PY -m json.tool || echo "health via 443 failed"

hdr "App health (localhost 8080)"
curl -sS --max-time 3 http://127.0.0.1:8080/health || echo "app 8080 unreachable"

hdr "Recent nginx errors"
sudo tail -n 25 /var/log/nginx/error.log || true

hdr "Recent app logs"
sudo journalctl -u tullman -n 40 --no-pager | tail -n +1
