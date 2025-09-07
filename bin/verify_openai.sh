#!/usr/bin/env bash
set -euo pipefail

# 1) Read key (not echoed)
read -s -p "OpenAI API key (sk-...): " KEY; echo

# 2) One-off Python ping using that key (no storage)
echo "[test] python ping"
OPENAI_API_KEY="$KEY" /home/kmages/tullman/venv/bin/python - <<'PY'
import os, sys
try:
    import openai
except ImportError:
    print("installing openai…", file=sys.stderr)
    raise SystemExit(1)
openai.api_key = os.environ['OPENAI_API_KEY']
try:
    openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":"ping"}],
        max_tokens=1,
    )
    print("OPENAI_OK")
except Exception as e:
    print("OPENAI_ERR:", type(e).__name__, str(e)[:120])
PY || {
  echo "[hint] If you saw 'installing openai…', run:" 
  echo "  source ~/tullman/venv/bin/activate && pip install -q --upgrade 'openai<1.0.0' && deactivate"
  exit 1
}

# 3) Raw curl ping (401 here means bad key or wrong scope)
echo "[test] curl ping"
RESP=$(curl -s -o /dev/null -w "%{http_code}" https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}],"max_tokens":1}')
echo "HTTP:$RESP"
if [ "$RESP" != "200" ]; then
  echo "[fail] HTTP $RESP from OpenAI — rotate the key or check org/project scope."
  exit 1
fi

# 4) Persist the key to systemd env (survives reboots)
echo "[write] /etc/systemd/system/tullman.env"
sudo tee /etc/systemd/system/tullman.env >/dev/null <<EOF
OPENAI_MODEL=gpt-5-thinking
OPENAI_API_KEY=$KEY
EOF
sudo chmod 600 /etc/systemd/system/tullman.env
sudo chown root:root /etc/systemd/system/tullman.env

# 5) Ensure unit loads env and restart
sudo mkdir -p /etc/systemd/system/tullman.service.d
sudo tee /etc/systemd/system/tullman.service.d/env.conf >/dev/null <<'EOF'
[Service]
EnvironmentFile=/etc/systemd/system/tullman.env
EOF
sudo systemctl daemon-reload
sudo systemctl restart tullman

# 6) Prove workers actually see the env (redacted)
echo "[env] workers"
for pid in $(pgrep -f 'gunicorn.*server:app'); do
  echo "==$pid=="
  sudo strings /proc/$pid/environ | grep -E 'OPENAI_(MODEL|API_KEY)' \
    | sed 's/\(OPENAI_API_KEY=\).*/\1***REDACTED***/'
done

# 7) Force a non-strategy GPT call and show the model used
echo "[check] chat (non-strategy)"
curl -sS -H 'Content-Type: application/json' \
  -d '{"prompt":"What did you change at Kendall College during the turnaround?","public":true}' \
  https://tullman.ai/chat | python3 -m json.tool || true

echo "[log] model path"
sudo journalctl -u tullman -n 120 --no-pager | grep -i 'kenifier model=' || true
