#!/usr/bin/env python3
from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path
from collections import OrderedDict, deque
import os, json, re, unicodedata, uuid

BASE     = Path.home() / "tullman"
FRONTEND = BASE / "frontend"
ASSETS   = FRONTEND / "assets"
DATA     = BASE / "data"
CONTENT  = DATA / "content" / "content.jsonl"

app = Flask(__name__)

# ---------- tiny corpus loader ----------
def iter_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    if not path.exists(): return []
    out=[]
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                out.append(json.loads(line))
                if limit and len(out) >= limit: break
            except: pass
    return out

def normalize(s: str) -> str:
    if not s: return ""
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if ord(ch) < 0x0300).lower()

def search_corpus(prompt: str, k: int = 6) -> tuple[str, list[dict]]:
    """Return concatenated context + URL-only sources (if present in JSON)."""
    rows = iter_jsonl(CONTENT, limit=50000)
    q = normalize(prompt)
    terms = set(re.findall(r"[a-zA-Z]{3,}", q))
    scored = []
    for r in rows:
        txt = (r.get("text") or "")
        low = txt.lower()
        # prefer Tullman material
        base = 5 if "tullman" in ((r.get("source_name") or "") + " " + low) else 0
        sc = base + sum(low.count(t) for t in terms)
        if sc > 0:
            scored.append((sc, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [r for _, r in scored[:k]]

    ctx = []
    sources = []
    seen_urls = set()
    for r in top:
        t = r.get("text") or ""
        if t.strip():
            ctx.append(t.strip())
        u = r.get("url")
        if u and u not in seen_urls:
            seen_urls.add(u)
            sources.append({"title": r.get("title") or r.get("source_name") or u, "url": u})
    return "\n\n".join(ctx)[:6000], sources

# ---------- sessions ----------
SESSIONS: "OrderedDict[str, deque[tuple[str,str]]]" = OrderedDict()
MAX_TURNS = 16
MAX_SESS  = 200

def get_session(sid: str | None):
    sid = sid or uuid.uuid4().hex
    sess = SESSIONS.get(sid)
    if sess is None:
        sess = deque(maxlen=MAX_TURNS)
        SESSIONS[sid] = sess
        if len(SESSIONS) > MAX_SESS:
            SESSIONS.popitem(last=False)
    else:
        SESSIONS.move_to_end(sid)
    return sid, sess

# ---------- GPT-5 rewriter (always) ----------
def gpt5_howard_markdown(prompt: str, context: str, sources: list[dict]) -> str:
    import openai, os
    openai.api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("OPENAI_MODEL", "gpt-5-thinking")

    sysmsg = (
        "You are Howard Tullman. Speak in first person (I, my). "
        "Be warm, candid, direct, optimistic, and concise. "
        "Return clean Markdown. Do not add a heading like '# Answer'."
    )

    src_md = ""
    if sources:
        src_md = "\n\nSOURCES (links you may cite):\n" + "\n".join(f"- {s.get('title')}: {s.get('url')}" for s in sources)

    user = f"""QUESTION:
{prompt}

CONTEXT:
{context or '(no additional context)'}
{src_md}
"""
    try:
        app.logger.info(f"kenifier model={model} remote=True")
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[{"role":"system","content":sysmsg},
                      {"role":"user","content":user}],
            temperature=0.2,
        )
        return (resp["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:
        app.logger.warning(f"gpt5_error: {e}")
        # curated fallback so site never breaks
        if "who is" in prompt.lower():
            return ("Hi — I’m Howard Tullman. I’m a Chicago-based entrepreneur, operator, and investor. "
                    "I led 1871, helped build Tribeca Flashpoint Academy, and turned around Kendall College. "
                    "Earlier I founded or ran CCC Information Services, Tunes.com, and The Cobalt Group. "
                    "I mentor founders, invest in scrappy teams, and I believe AI is now table stakes for every business and for individuals.")
        return "Hi — I’m Howard Tullman. Let’s get specific. What outcome are you aiming for, and what constraint is in your way?"

# ---------- routes ----------
@app.get("/health")
def health():
    rows = iter_jsonl(CONTENT, limit=500000)
    counts={}
    for r in rows:
        t=r.get("source_type","unknown")
        counts[t]=counts.get(t,0)+1
    return jsonify({"ok": True, "total": sum(counts.values()), "counts": counts})

@app.get("/assets/<path:fname>")
def assets(fname):
    return send_from_directory(ASSETS, fname)

@app.get("/")
def home():
    html = FRONTEND / "public.html"
    if html.exists():
        return send_from_directory(html.parent, html.name)
    return jsonify({"ok": True, "msg": "Public page missing"}), 200

@app.post("/chat")
def chat():
    j = request.get_json(force=True, silent=True) or {}
    q = (j.get("prompt") or "").strip()
    if not q:
        return jsonify({"session_id": j.get("session_id"), "answer":"Ask a question first.","sources":[]})
    sid, hist = get_session(j.get("session_id"))
    ctx_pairs = list(hist)[-8:]
    prior = " ".join(f"{r}: {c}" for r,c in ctx_pairs)

    # JSON-first context; URLs only in public Sources
    ctx, sources = search_corpus(q)
    answer = gpt5_howard_markdown(q, (prior + "\n\n" + ctx).strip(), sources)
    hist.append(("user", q)); hist.append(("assistant", answer))
    return jsonify({"session_id": sid, "answer": answer, "sources": sources})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
