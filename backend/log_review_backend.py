import os, json, re, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, unquote
import requests

from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from retrieve_route import setup_retrieve
from werkzeug.utils import secure_filename

# ========= Config =========
DB_PATH       = os.path.expanduser('~/tullman/app.db')
ARCHIVE_PATH  = os.path.expanduser('~/tullman/archive/archive.jsonl')
RULES_PATH    = os.path.expanduser('~/tullman/rules.json')
FRONTEND_DIR  = os.path.expanduser('~/tullman/frontend')
CORPUS_DIR    = os.path.expanduser('~/tullman/corpus')
ASSETS_DIR    = '/var/www/tullman/assets'  # golden.json / rules.json are served here

Path(ARCHIVE_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(FRONTEND_DIR).mkdir(parents=True, exist_ok=True)
Path(CORPUS_DIR).mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; TullmanBackend/1.0; +https://tullman.ai)"}

HOWARD_SITES = [
    "howardtullman.com",
    "www.howardtullman.com",
    "inc.com/howard-tullman",
    "www.inc.com/howard-tullman",
    "blogspot.tullman.com",
    "www.blogspot.tullman.com",
    "en.wikipedia.org/wiki/Howard_Tullman",
]

# ========= Flask / DB =========
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class QAPair(db.Model):
    __tablename__ = 'qa_pairs'
    id         = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    date_id    = db.Column(db.String(32), index=True)
    question   = db.Column(db.Text, nullable=False)
    answer     = db.Column(db.Text, default='')
    status     = db.Column(db.String(32), default='active', index=True)  # active/restored/queued/in_loop2/archived/deleted
    is_excluded= db.Column(db.Boolean, default=False)
    def as_dict(self):
        return {
            "id": self.id, "date_id": self.date_id,
            "created_at": self.created_at.isoformat()+"Z",
            "question": self.question, "answer": self.answer,
            "status": self.status, "is_excluded": self.is_excluded
        }

class Example(db.Model):
    __tablename__ = 'examples'
    id         = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    primary_question = db.Column(db.Text, nullable=False)
    answer     = db.Column(db.Text, nullable=False)
    locked     = db.Column(db.Boolean, default=True)
    active     = db.Column(db.Boolean, default=True)
    def as_dict(self):
        return {
            "id": self.id, "created_at": self.created_at.isoformat()+"Z",
            "primary_question": self.primary_question, "answer": self.answer,
            "locked": self.locked, "active": self.active
        }

with app.app_context():
    db.create_all()

setup_retrieve(app, db, Example)

# ========= Helpers =========
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_rules():
    # site-served rules override local file if present
    served = os.path.join(ASSETS_DIR, "rules.json")
    if os.path.isfile(served):
        return load_json(served, {})
    return load_json(RULES_PATH, {})

def strip_html(txt):
    return re.sub(r'<[^>]+>', ' ', txt or '')

def golden_pairs():
    served = os.path.join(ASSETS_DIR, "golden.json")
    data = load_json(served, [])
    rows = []
    if isinstance(data, list):
        for d in data:
            q = (d.get("q") or "").strip()
            a = (d.get("a") or "").strip()
            if q: rows.append((q.lower(), a))
    elif isinstance(data, dict):
        for q,a in data.items():
            rows.append((str(q).strip().lower(), str(a)))
    return rows

def golden_lookup(prompt):
    p = (prompt or "").strip().lower()
    pairs = golden_pairs()
    for q,a in pairs:
        if q == p: return a
    for q,a in pairs:
        if p in q or q in p: return a
    return None

def search_corpus(prompt):
    """Return {'file': path, 'snippet': text} or None."""
    try:
        p = (prompt or "").strip().lower()
        best = None
        for root, _, files in os.walk(CORPUS_DIR):
            for name in files:
                if not name.lower().endswith((".txt",".md",".html",".htm",".json",".csv",".mdx",".rst",".yaml",".yml",".ini",".cfg",".conf",".log",".sql",".tsv",".pdf")):
                    continue
                fp = os.path.join(root, name)
                try:
                    raw = Path(fp).read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    try:
                        with open(fp, "rb") as f: raw = f.read().decode("utf-8", "ignore")
                    except Exception:
                        continue
                text = strip_html(raw)
                hit = text.lower().find(p)
                if hit != -1:
                    start = max(0, hit-200); end = min(len(text), hit+200)
                    return {"file": fp, "snippet": text[start:end].strip()}
        return best
    except Exception:
        return None

def ddg_links(query, timeout=12, limit=5):
    """DuckDuckGo HTML search; extract result URLs (handles /l/?uddg= links)."""
    try:
        url = "https://duckduckgo.com/html/?" + urlencode({"q": query})
        r = requests.get(url, timeout=timeout, headers=UA)
        r.raise_for_status()
        html = r.text
        links = []

        # Pattern 1: direct href="http..."
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            links.append(m.group(1))

        # Pattern 2: DDG redirect /l/?uddg=...
        for m in re.finditer(r'href="/l/\?[^"]*uddg=([^"&]+)', html):
            links.append(unquote(m.group(1)))

        # de-dup, keep order
        seen, out = set(), []
        for u in links:
            if u not in seen:
                seen.add(u); out.append(u)
        return out[:limit]
    except Exception:
        return []

def fetch_via_proxy(url, timeout=15):
    """Fetch text through r.jina.ai readability proxy, so 403s are bypassed."""
    try:
        proxy = "https://r.jina.ai/http://" + url.replace("https://","").replace("http://","")
        pr = requests.get(proxy, timeout=timeout, headers=UA)
        if pr.status_code == 200:
            text = re.sub(r"\s+", " ", pr.text).strip()
            return text
    except Exception:
        pass
    return ""

def fetch_readable(url, timeout=15):
    """Best-effort readable text from URL; try direct then proxy."""
    try:
        # Special: Wikipedia summary
        if "wikipedia.org/wiki/" in url:
            title = url.split("/wiki/",1)[-1].replace(" ", "_")
            api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
            wr = requests.get(api, timeout=timeout, headers=UA)
            if wr.status_code == 200:
                j = wr.json()
                txt = (j.get("extract") or "")
                if len(txt) >= 180: return txt[:20000]
        # Try proxy first (more reliable)
        text = fetch_via_proxy(url, timeout=timeout)
        if len(text) >= 180: return text[:20000]
        return ""
    except Exception:
        return ""

def internet_fallback(prompt, budget_sec=60.0):
    """Find Howard-related sources and weave/return answer (dict)."""
    t0 = time.monotonic()
    hits = []

    # Wave 1: explicit Howard sources
    for site in HOWARD_SITES:
        if time.monotonic() - t0 > budget_sec*0.45: break
        urls = ddg_links(f"site:{site} {prompt}", timeout=12, limit=3)
        for u in urls:
            if time.monotonic() - t0 > budget_sec*0.65: break
            text = fetch_readable(u, timeout=15)
            if len(text) >= 180:
                hits.append({"url": u, "text": text})
            if len(hits) >= 4: break
        if len(hits) >= 4: break

    # Wave 2: broader queries
    if len(hits) < 2 and time.monotonic() - t0 <= budget_sec*0.85:
        variants = [
            f'"Howard Tullman" {prompt}',
            f'Howard Tullman on {prompt}',
            f'Howard Tullman advice {prompt}',
            f'"Howard Tullman" quote {prompt}',
            f'site:inc.com/howard-tullman {prompt}',
            f'site:blogspot.tullman.com {prompt}',
            f'site:en.wikipedia.org/wiki "Howard Tullman" {prompt}',
        ]
        seen = {h["url"] for h in hits}
        for q in variants:
            if time.monotonic() - t0 > budget_sec*0.92 or len(hits) >= 5: break
            urls = ddg_links(q, timeout=12, limit=4)
            for u in urls:
                if u in seen: continue
                seen.add(u)
                text = fetch_readable(u, timeout=15)
                if len(text) >= 180:
                    hits.append({"url": u, "text": text})
                if time.monotonic() - t0 > budget_sec*0.96 or len(hits) >= 5: break

    # Build answer: GPT if possible, else stitched snippet
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_APIKEY")
    if hits and api_key and time.monotonic() - t0 <= budget_sec*0.98:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            # context
            parts = []
            for h in hits:
                excerpt = h["text"][:1400]
                parts.append(f"SOURCE: {h['url']}\nEXCERPT:\n{excerpt}\n")
            ctx = ("QUESTION: " + prompt + "\n\n" + "\n\n".join(parts)).strip()
            messages = [
                {"role":"system","content":(
                    "You are Howard Tullman. Answer crisply in his voice. "
                    "Weave a relevant quote/anecdote from the supplied sources (if any). "
                    "Avoid fluff. Use one subtle inline cite like (source: URL). "
                    "If no relevant source exists, answer from first principles in Howard’s voice."
                )},
                {"role":"user","content": ctx},
            ]
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.35,
                max_tokens=900,
                timeout=max(5, int(budget_sec - (time.monotonic() - t0)) - 2)
            )
            answer = (resp.choices[0].message.content or "").strip()
            return {"answer": answer, "source": "internet-howard", "sources": [h["url"] for h in hits]}
        except Exception:
            pass

    if hits:
        best = hits[0]
        snip = best["text"][:800]
        stitched = f"{snip} … (source: {best['url']})"
        return {"answer": stitched, "source": "internet-snippet", "sources": [best["url"]]}

    return {"answer": "(no online source found yet)", "source": "internet-none", "sources": []}

def rules_match(patterns, prompt):
    if not patterns: return False
    for pat in patterns:
        try:
            if re.search(pat, prompt, flags=re.I): return True
        except re.error:
            if pat.lower() in prompt.lower(): return True
    return False

# ========= API =========
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "log_review_backend"})

@app.route("/api/rules", methods=["GET","PUT"])
def rules():
    if request.method == "GET":
        # prefer served rules.json if present
        served = os.path.join(ASSETS_DIR, "rules.json")
        if os.path.isfile(served):
            txt = Path(served).read_text(encoding="utf-8", errors="ignore")
        else:
            txt = Path(RULES_PATH).read_text(encoding="utf-8", errors="ignore") if os.path.isfile(RULES_PATH) else ""
        return jsonify({"rules": txt})
    data = request.get_json(force=True) or {}
    Path(RULES_PATH).write_text(data.get("rules") or "", encoding="utf-8")
    return jsonify({"ok": True})

@app.route("/api/examples", methods=["GET"])
def examples_list_api():
    items = Example.query.order_by(Example.created_at.asc()).all()
    return jsonify({"items":[e.as_dict() for e in items], "count":len(items)})

@app.route("/api/examples/match", methods=["GET"])
def examples_match_api():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"matched": False, "query": ""}), 400
    item = Example.query.filter(Example.primary_question.ilike(f"%{q}%")).first()
    if not item:
        return jsonify({"matched": False, "query": q})
    return jsonify({"matched": True, "query": q, "example": item.as_dict()})


@app.route("/frontend/<path:fname>", methods=["GET"])
def frontend_file(fname):
    return send_from_directory(FRONTEND_DIR, fname)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5057, debug=False)
