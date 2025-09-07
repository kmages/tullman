Tullman.ai — Request flow (stable)

[ Browser UI ]
  /home/kmages/tullman/frontend/public.html
    └─ JS POST /retrieve  { "prompt": "<user question>" }

[ Nginx TLS vhost ]  /etc/nginx/sites-enabled/tullman
  • location = /            → try_files /public.html
  • location = /admin       → alias /var/www/tullman/assets/admin.html
  • include tullman_meta.conf → /meta → http://127.0.0.1:5100/meta
  • location ^~ /retrieve   → proxy_pass http://127.0.0.1:5100

[ Backend (Gunicorn) ]
  systemd service: backend.service → gunicorn -w 2 -b 127.0.0.1:5100 app:app
  app.py bootstraps Flask + installs the /retrieve hotfix from:
    /home/kmages/backend/_retrieve_hotfix.py

[ /retrieve hotfix — decision order ]
  0) Blocklist (free will/religion/meaning of life) → fixed rabbi line
  1) Build CONTEXT:
     • identity override (Who is Howard…, AI strategy, Kendall) OR
     • best example from /home/kmages/backend/voiceprint_seed.jsonl (Jaccard ≥ 0.42)
  2) GPT WEAVE (ALWAYS):
     • System: /home/kmages/backend/voiceprint_staging.txt (or _prod.txt)
     • User:   "Reference to weave:\n<CONTEXT>\n\nPrompt:\n<PROMPT>\n\nWrite one concise, first-person answer…"
     • Model:  $OPENAI_MODEL (fallback to gpt-4o-mini if unavailable)
  3) If GPT unavailable: identity OR example OR rule-of-thumb fallback (e.g., lifespan) OR short stub

[ Admin ]
  /var/www/tullman/assets/admin.html (immutable)
    • Save Rules → /admin/api/voiceprint → write voiceprint_staging.txt
    • Save Q&A   → /admin/api/examples_text → write voiceprint_seed.jsonl
    • Rebuild Tuner → /tuner/rebuild (optional seed builder)

Immutables (edit requires: chattr -i … ; … ; chattr +i ; nginx reload)
  • /home/kmages/tullman/frontend/public.html
  • /var/www/tullman/assets/admin.html
  • /var/www/tullman/assets/loop.html

Smoke test:  bash /tmp/tullman-smoke.sh
