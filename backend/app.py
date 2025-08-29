from flask import Flask, request, jsonify
import os, re, json, datetime, subprocess, pickle

app = Flask(__name__)
SERVICE_TAG = "tullman-backend v2.4 (hotfix+gpt+lifespan)"

BASE          = "/home/kmages/backend"
SEED_JSONL    = os.path.join(BASE, "voiceprint_seed.jsonl")
SEM_PROD      = os.path.join(BASE, "semantic_prod.pkl")
VOICE_STG     = os.path.join(BASE, "voiceprint_staging.txt")
VOICE_PROD    = os.path.join(BASE, "voiceprint_prod.txt")
GOLDEN_JSONL  = "/home/kmages/golden.jsonl"
TUNER_PY      = os.path.join(BASE, "tuner_build_seed.py")
VENV_PY       = os.path.join(BASE, "venv", "bin", "python")

def now(): return datetime.datetime.now().isoformat(timespec="seconds")

# -------- health
@app.route("/meta")
def meta():
    rules=[r"\bfree[\s\-]?will\b",r"\breligion(s|al)?\b",r"\bfaith\b",r"\bgod\b|\bgods\b|\bdeity\b",
           r"\bmeaning\s+of\s+life\b",r"\bpurpose\s+of\s+life\b",r"\bafterlife\b|\bheaven\b|\bhell\b",
           r"\bdeath\b|\bdying\b|\bmortality\b",r"\bphilosoph(y|ical|er)\b"]
    return jsonify({"service": SERVICE_TAG, "rules": rules, "ts": now()})

# -------- small utils for examples
def load_pairs():
    pairs=[]
    try:
        with open(SEED_JSONL,"r",encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if not line: continue
                try:
                    j=json.loads(line)
                    q=(j.get("prompt") or "").strip()
                    a=(j.get("response") or "").strip()
                    if q and a: pairs.append((q,a))
                except: pass
    except: pass
    return pairs

STOP = set("""
a an and are as at be but by for from had has have i if in is it its of on or our so than that the their then there these they this to under was were what when where which who why will with you your
""".split())

_word = re.compile(r"[a-z0-9]+")

def tokens(s):
    return {t for t in _word.findall(s.lower()) if len(t)>2 and t not in STOP}

def best_match_answer(q):
    tq = tokens(q)
    if not tq: return None
    pairs = load_pairs()
    best=None; best_score=0.0
    for pq,pa in pairs:
        tp = tokens(pq)
        if not tp: continue
        jac = len(tq & tp) / max(1, len(tq | tp))
        # small boost if a rare keyword appears in both
        if "kendall" in tq and "kendall" in tp: jac += 0.25
        if jac > best_score:
            best_score = jac; best = pa
    # be stricter to avoid bad grabs
    return best if best_score >= 0.42 else None

# -------- retrieve (identity → topic → examples → fallback), plus rabbi rule
BLOCK = re.compile(r"(free\s*-?\s*will|religion(s|al)?|faith|\bgod(s)?\b|deity|meaning\s+of\s+life|purpose\s+of\s+life|afterlife|heaven|hell|death|dying|mortality|philosoph(y|ical|er))", re.I)
FIXED = "I am not a rabbi, priest or philosopher and I’m also in a hurry so questions like this are not a good use of my time or yours."

IDENTITY_OVERRIDES = [
    (re.compile(r"\bwho\s+is\s+howard\s+tullman\??", re.I),
     "I’m a serial entrepreneur, investor, and educator. I’ve led multiple tech companies, ran 1871 in Chicago, and spent decades building teams, backing founders, and writing about execution."),
    (re.compile(r"\bwhy\b.*\bai\s+strategy\b|\bwhy\s+do\s+i\s+need\s+an\s+ai\s+strategy\??", re.I),
     "Because it drives results: faster execution, lower cost, and clear differentiation. Start with a 12-month roadmap, pick 2–3 high-value use cases, ship a small win in 30–60 days, then scale what works."),
    (re.compile(r"\b(kendall)\b.*(changed|change|under\s+your\s+leadership)", re.I),
     "At Kendall I focused on speed, relevance, and outcomes — tighter industry ties, more real-world projects, measurable results, and higher expectations for students, faculty, and partners."),
]

TOPIC_OVERRIDES = [
    (re.compile(r"\b(relativity|einstein)\b.*\b(ten|10|child|kid|kids|student)\b|\bteach\b.*\brelativity\b", re.I),
     "Imagine you’re on a very fast train. You toss a ball; to you it looks normal, but to someone standing outside it moves differently. Relativity says time and distance can look different depending on how fast you’re moving and how strong gravity is. Go faster or be near something heavy, and clocks tick a tiny bit differently. That’s it: motion and gravity change what we see as time and space."),
]


# ===== patched /retrieve (identity → topic → examples → fallback) =====
import json as _json, re as _re

_R_SEED = "/home/kmages/backend/voiceprint_seed.jsonl"

def _r_load_pairs():
    pairs=[]
    try:
        with open(_R_SEED,"r",encoding="utf-8") as f:
            for ln in f:
                ln=ln.strip()
                if not ln: continue
                try:
                    j=_json.loads(ln)
                    q=(j.get("prompt") or "").strip()
                    a=(j.get("response") or "").strip()
                    if q and a: pairs.append((q,a))
                except: pass
    except: pass
    return pairs

_R_STOP = set("a an and are as at be but by for from had has have i if in is it its of on or our so than that the their then there these they this to under was were what when where which who why will with you your".split())
_R_WORD = _re.compile(r"[a-z0-9]+")

def _r_tokens(s):
    return {t for t in _R_WORD.findall((s or '').lower()) if len(t)>2 and t not in _R_STOP}

def _r_best_match(q):
    tq = _r_tokens(q)
    if not tq: return None
    best=None; best_score=0.0
    for pq,pa in _r_load_pairs():
        tp = _r_tokens(pq)
        if not tp: continue
        jac = len(tq & tp) / max(1, len(tq | tp))
        if "kendall" in tq and "kendall" in tp:
            jac += 0.25
        if jac > best_score:
            best_score = jac; best = pa
    return best if best_score >= 0.42 else None  # stricter to avoid bad grabs

_R_BLOCK = _re.compile(r"(free\s*-?\s*will|religion(s|al)?|faith|\bgod(s)?\b|deity|meaning\s+of\s+life|purpose\s+of\s+life|afterlife|heaven|hell|death|dying|mortality|philosoph(y|ical|er))", _re.I)
_R_FIXED = "I am not a rabbi, priest or philosopher and I’m also in a hurry so questions like this are not a good use of my time or yours."

_R_IDENTS = [
    (_re.compile(r"\bwho\s+is\s+howard\s+tullman\??", _re.I),
     "I’m a serial entrepreneur, investor, and educator. I’ve led multiple tech companies, ran 1871 in Chicago, and spent decades building teams, backing founders, and writing about execution."),
    (_re.compile(r"\bwhy\b.*\bai\s+strategy\b|\bwhy\s+do\s+i\s+need\s+an\s+ai\s+strategy\??", _re.I),
     "Because it drives results: faster execution, lower cost, and clear differentiation. Start with a 12-month roadmap, pick 2–3 high-value use cases, ship a small win in 30–60 days, then scale what works."),
    (_re.compile(r"\b(kendall)\b.*(changed|change|under\s+your\s+leadership)", _re.I),
     "At Kendall I focused on speed, relevance, and outcomes—tighter industry ties, more real-world projects, measurable results, and higher expectations for students, faculty, and partners."),
]

_R_TOPICS = [
    (_re.compile(r"\b(relativity|einstein)\b.*\b(ten|10|child|kid|kids|student)\b|\bteach\b.*\brelativity\b", _re.I),
     "Imagine you’re on a very fast train. You toss a ball; to you it looks normal, but to someone outside it moves differently. Relativity says time and distance can look different depending on speed and gravity. Go faster or be near something heavy, and clocks tick a little differently. That’s it: motion and gravity change what we see as time and space."),
]

@app.route("/retrieve", methods=["POST"])
def retrieve():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or data.get("q") or data.get("text") or "").strip()

    if _R_BLOCK.search(prompt or ""):
        return jsonify({"answer": _R_FIXED, "response": _R_FIXED, "ruled": True, "service": SERVICE_TAG})

    pl = (prompt or "").lower()
    for rx,ans in _R_IDENTS:
        if rx.search(pl):
            return jsonify({"answer": ans, "response": ans, "ruled": False, "service": SERVICE_TAG})

    for rx,ans in _R_TOPICS:
        if rx.search(pl):
            return jsonify({"answer": ans, "response": ans, "ruled": False, "service": SERVICE_TAG})

    ex = _r_best_match(prompt)
    if ex:
        return jsonify({"answer": ex, "response": ex, "ruled": False, "service": SERVICE_TAG})

    fb = "Give me one detail (timeframe, scope, or result) and I’ll answer directly."
    return jsonify({"answer": fb, "response": fb, "ruled": False, "service": SERVICE_TAG})
# ===== end patched /retrieve =====

@app.route("/admin/api/examples_text", methods=["GET","POST"])
def api_examples_text():
    if request.method == "GET":
        out=[]
        for q,a in load_pairs():
            out.append(f"Q: {q}\nA: {a}")
        return jsonify({"ok": True, "text": ("\n\n".join(out))})
    raw = (request.form.get("text") or (request.json or {}).get("text") or "").strip()
    lines=[ln.rstrip() for ln in raw.splitlines()]
    pairs=[]; q=a=None
    for ln in lines+[""]:
        if ln.startswith("Q:"):
            if q and a: pairs.append((q.strip(), a.strip()))
            q=ln[2:].strip(); a=None
        elif ln.startswith("A:"):
            a=ln[2:].strip()
        elif ln=="" and q and a:
            pairs.append((q.strip(), a.strip())); q=a=None
        else:
            if a is not None and ln: a=(a+"\n"+ln).strip()
            elif q is not None and ln: q=(q+"\n"+ln).strip()
    try:
        if os.path.exists(SEED_JSONL): os.rename(SEED_JSONL, SEED_JSONL+".bak")
    except Exception: pass
    with open(SEED_JSONL,"w",encoding="utf-8") as f:
        for qp,ar in pairs:
            f.write(json.dumps({"prompt":qp,"response":ar,"date":now(),"source":"Howard edit"}, ensure_ascii=False)+"\n")
    return jsonify({"ok": True, "count": len(pairs)})

@app.route("/admin/api/examples_restore_from_prod", methods=["POST"])
def api_examples_restore_from_prod():
    if not os.path.exists(SEM_PROD):
        return jsonify({"ok": False, "error": "semantic_prod.pkl not found"}), 404
    try:
        obj = pickle.load(open(SEM_PROD,"rb"))
        pairs = obj.get("pairs") or []
    except Exception as e:
        return jsonify({"ok": False, "error": f"read error: {e}"}), 500
    if not pairs:
        return jsonify({"ok": False, "error": "no pairs in prod index"}), 400
    try:
        if os.path.exists(SEED_JSONL): os.rename(SEED_JSONL, SEED_JSONL+".bak")
    except Exception: pass
    with open(SEED_JSONL,"w",encoding="utf-8") as f:
        for q,a in pairs:
            if q and a: f.write(json.dumps({"prompt":q,"response":a,"date":now(),"source":"restored_from_prod"}, ensure_ascii=False)+"\n")
    return jsonify({"ok": True, "count": len([1 for q,a in pairs if q and a])})

@app.route("/admin/api/voiceprint", methods=["GET","POST"])
def api_voiceprint():
    if request.method=="GET":
        for pth in (VOICE_STG, VOICE_PROD):
            if os.path.exists(pth):
                try:
                    t=open(pth,"r",encoding="utf-8").read()
                    if t.strip(): return jsonify({"ok":True,"text":t,"path":pth})
                except: pass
        return jsonify({"ok":True,"text":"","path":VOICE_STG})
    text = (request.form.get("text") or (request.json or {}).get("text") or "").rstrip()
    mode = (request.form.get("mode") or (request.json or {}).get("mode") or "replace").lower()
    old=""
    if mode=="append" and os.path.exists(VOICE_STG):
        try: old=open(VOICE_STG,"r",encoding="utf-8").read().rstrip()
        except: old=""
    new = (old + ("\n\n" if old and text else "") + text).rstrip()+"\n"
    with open(VOICE_STG,"w",encoding="utf-8") as f: f.write(new)
    return jsonify({"ok":True,"path":VOICE_STG,"bytes":len(new.encode())})

@app.route("/admin/api/index_text", methods=["POST"])
def api_index_text():
    title=(request.form.get("title") or (request.json or {}).get("title") or "(admin note)").strip()
    text =(request.form.get("text")  or (request.json or {}).get("text")  or "").strip()
    if not text: return jsonify({"ok":False,"error":"empty text"}), 400
    os.makedirs(os.path.dirname(GOLDEN_JSONL), exist_ok=True)
    with open(GOLDEN_JSONL,"a",encoding="utf-8") as f:
        f.write(json.dumps({"title":title,"text":text,"date":now(),"source":"admin_index_text"}, ensure_ascii=False)+"\n")
    return jsonify({"ok":True})

@app.route("/tuner/rebuild", methods=["POST"])
def tuner_rebuild():
    log=[]
    if os.path.exists(TUNER_PY):
        py = VENV_PY if os.path.exists(VENV_PY) else "python3"
        try:
            cp = subprocess.run([py, TUNER_PY], capture_output=True, text=True, timeout=90)
            log.append(cp.stdout[-2000:])
        except Exception as e:
            log.append(str(e))
    return jsonify({"ok": True, "log": "\n".join(log)})

@app.route("/admin/api/review_count")
def review_count():
    qfile = os.path.join(BASE,"admin_queue.jsonl")
    counts = {"pending":0,"approved":0,"rejected":0,"total":0}
    try:
        with open(qfile,"r",encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if not line: continue
                try: j=json.loads(line)
                except Exception: continue
                st=(j.get("status") or "pending").lower()
                counts["total"] += 1
                if st=="approved": counts["approved"]+=1
                elif st=="rejected": counts["rejected"]+=1
                else: counts["pending"]+=1
    except Exception: pass
    return jsonify({"ok": True, "counts": counts})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100)


# === /retrieve hotfix (GPT-backed + rule-of-thumb fallback) ===
import json as _J, re as _R, os as _OS
from pathlib import Path as _P

_R_SEED = "/home/kmages/backend/voiceprint_seed.jsonl"
_VOICE_STG = "/home/kmages/backend/voiceprint_staging.txt"
_VOICE_PROD = "/home/kmages/backend/voiceprint_prod.txt"

def _r_seed_pairs():
    out=[]
    try:
        with open(_R_SEED,"r",encoding="utf-8") as f:
            for ln in f:
                ln=ln.strip()
                if not ln: continue
                try:
                    j=_J.loads(ln)
                    q=(j.get("prompt") or "").strip()
                    a=(j.get("response") or "").strip()
                    if q and a: out.append((q,a))
                except: pass
    except: pass
    return out

_R_STOP=set("a an and are as at be but by for from had has have i if in is it its of on or our so than that the their then there these they this to under was were what when where which who why will with you your".split())
_RW=_R.compile(r"[a-z0-9]+")
def _tok(x): return {t for t in _RW.findall((x or "").lower()) if len(t)>2 and t not in _R_STOP}

def _best(q):
    tq=_tok(q)
    if not tq: return None
    best=None; sc=0.0
    for pq,pa in _r_seed_pairs():
        tp=_tok(pq)
        if not tp: continue
        jac=len(tq & tp)/max(1,len(tq|tp))
        if "kendall" in tq and "kendall" in tp: jac += 0.25
        if jac>sc: sc=jac; best=pa
    return best if sc>=0.42 else None

# hard rule block
_R_BLOCK=_R.compile(r"(free\s*-?\s*will|religion(s|al)?|faith|\bgod(s)?\b|deity|meaning\s+of\s+life|purpose\s+of\s+life|afterlife|heaven|hell|death|dying|mortality|philosoph(y|ical|er))",_R.I)
_R_FIXED="I am not a rabbi, priest or philosopher and I’m also in a hurry so questions like this are not a good use of my time or yours."

# identity / topics
def _ident(pl:str):
    if _R.search(r"\bwho\s+is\s+howard\s+tullman\??", pl):
        return "I’m a serial entrepreneur, investor, and educator. I’ve led multiple tech companies, ran 1871 in Chicago, and spent decades building teams, backing founders, and writing about execution."
    if _R.search(r"\bwhy\b.*\bai\s+strategy\b|\bwhy\s+do\s+i\s+need\s+an\s+ai\s+strategy\??", pl):
        return "Because it drives results: faster execution, lower cost, and clear differentiation. Start with a 12-month roadmap, pick 2–3 high-value use cases, ship a small win in 30–60 days, then scale what works."
    if _R.search(r"\b(kendall)\b.*(changed|change|under\s+your\s+leadership)", pl):
        return "At Kendall I focused on speed, relevance, and outcomes—tighter industry ties, more real-world projects, measurable results, and higher expectations for students, faculty, and partners."
    if _R.search(r"\b(relativity|einstein)\b.*\b(ten|10|child|kid|kids|student)\b|\bteach\b.*\brelativity\b", pl):
        return "Imagine you’re on a very fast train. You toss a ball; to you it looks normal, but to someone outside it moves differently. Relativity says time and distance can look different depending on speed and gravity. Go faster or be near something heavy, and clocks tick a little differently. That’s it: motion and gravity change what we see as time and space."
    return None

def _voiceprint():
    for pth in (_VOICE_STG, _VOICE_PROD):
        try:
            t=_P(pth).read_text(encoding="utf-8").strip()
            if t: return t
        except: pass
    return ("SYSTEM: Rewrite answers in Howard Tullman’s voice.\n"
            "Tone: first person; direct; concise; no fluff; no hedging.\n"
            "Output: one concise first-person answer only.")

# small rule-of-thumb fallback for common “how long do X live?”
def _lifespan_stub(pl:str):
    if _R.search(r"\bhow\s+long\s+do\s+dogs?\s+live", pl):
        return "Most dogs live about 10–13 years. Smaller breeds often reach 12–16; giant breeds are closer to 7–10. Care, genetics, and size drive the spread."
    if _R.search(r"\bhow\s+long\s+do\s+cats?\s+live", pl):
        return "Indoor cats often reach 12–15 years and many live past 16; outdoor cats trend shorter. Care and genetics matter."
    if _R.search(r"\bhow\s+long\s+do\s+humans?\s+live|\blife\s+expectancy\b", pl):
        return "In the U.S., life expectancy is roughly mid-70s to low-80s depending on sex and region. Health, lifestyle, and access drive the spread."
    return None

# optional OpenAI v1 client
_client=None
def _gpt_ans(prompt:str):
    global _client
    try:
        from openai import OpenAI
    except Exception:
        return None
    try:
        if _client is None: _client = OpenAI()
        model = _OS.getenv("OPENAI_MODEL","gpt-4o-mini")
        sys = _voiceprint()
        r = _client.chat.completions.create(
            model=model, temperature=0.3,
            messages=[{"role":"system","content":sys},
                      {"role":"user","content":prompt}],
        )
        txt = (r.choices[0].message.content or "").strip()
        return txt or None
    except Exception:
        return None

@app.before_request
def _intercept_retrieve():
    try:
        if request.path!="/retrieve" or request.method!="POST":
            return None
        data=request.get_json(silent=True) or {}
        prompt=(data.get("prompt") or data.get("q") or data.get("text") or "").strip()

        if _R_BLOCK.search(prompt or ""):
            return jsonify({"answer":_R_FIXED,"response":_R_FIXED,"ruled":True,"service":SERVICE_TAG})

        pl=(prompt or "").lower()
        ans = _ident(pl) or _best(prompt) or _lifespan_stub(pl) or _gpt_ans(prompt)
        if not ans:
            ans="Give me one detail (timeframe, scope, or result) and I’ll answer directly."
        return jsonify({"answer":ans,"response":ans,"ruled":False,"service":SERVICE_TAG})
    except Exception:
        return None
# === end /retrieve hotfix ===



# register retrieve hotfix without touching existing handlers
try:
    import _retrieve_hotfix as __rh
    __rh.install(app, SERVICE_TAG)
except Exception:
    pass


# --- force /retrieve to always return JSON ---
from flask import Response
@app.after_request
def _force_json_retrieve(r):
    try:
        if request.path == "/retrieve":
            body = r.get_data(as_text=True)
            # If not JSON, wrap it
            if not body.strip().startswith("{"):
                import json
                wrapped = json.dumps({
                    "answer": body.strip(),
                    "response": body.strip(),
                    "ruled": False,
                    "service": SERVICE_TAG
                })
                r.set_data(wrapped)
                r.mimetype = "application/json"
            else:
                # ensure the correct mimetype
                r.mimetype = "application/json"
    except Exception:
        pass
    return r


import json as __J, re as __R
# --- First-person rewriter: keeps bullets; converts openers & bullet lines to "I ..." ---
def _tullman_ivoice(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    # Paragraph openers
    s = __R.sub(r'(?im)^\s*Chicago\s+is\b', 'I love Chicago because it is', s)
    s = __R.sub(r'(?im)^\s*Chicago\s+has\b', 'I value Chicago because it has', s)
    s = __R.sub(r'(?im)^\s*The\s+city\s+is\b', 'I love the city because it is', s)
    s = __R.sub(r'(?im)^\s*The\s+city\s+has\b', 'I value the city because it has', s)
    s = __R.sub(r'(?im)^\s*It\s+is\b', 'I love it because it is', s)
    s = __R.sub(r'(?im)^\s*It\s+has\b', 'I value it because it has', s)

    # Bullets (numbered or symbol) -> ensure "I ..." on each
    def _fix(line: str) -> str:
        core = __R.sub(r'^\s*(?:\d+\.\s*|[-*•]\s*)', '', line)              # strip bullet token
        core = __R.sub(r'^\s*\*\*[^*]+\*\*\s*:\s*', '', core)               # drop bold lead-in
        core = __R.sub(r'^(T|t)he\s+city\b', 'I', core)
        core = __R.sub(r'^Chicago\b', 'I love Chicago', core)
        core = __R.sub(r'\s{2,}', ' ', core).strip()
        if core and not __R.match(r'(?i)^i\b', core):
            core = 'I ' + core[0].lower() + core[1:]
        return '- ' + core if core else '- I like it.'
    s = __R.sub(r'(?m)^\s*(?:\d+\.\s*|[-*•]\s*).*$',
                lambda m: _fix(m.group(0)), s)

    s = __R.sub(r'[ \t]{2,}', ' ', s)    # normalize spacing
    return s.strip()

# --- Force /retrieve to always return JSON and apply I-voice right before sending ---
from flask import Response
@app.after_request
def _tullman_force_json_and_ivoice(r):
    try:
        if request.path == "/retrieve":
            body = r.get_data(as_text=True)

            # Ensure JSON
            if not (body.strip().startswith("{") and body.strip().endswith("}")):
                wrapped = __J.dumps({
                    "answer": body.strip(),
                    "response": body.strip(),
                    "ruled": False,
                    "service": SERVICE_TAG
                })
                body = wrapped

            # Apply I-voice to answer/response fields
            try:
                obj = __J.loads(body)
                if isinstance(obj, dict) and "answer" in obj:
                    ans = obj.get("answer","")
                    resp = obj.get("response","")
                    obj["answer"] = ans
                    obj["response"] = resp
                    body = __J.dumps(obj)
            except Exception:
                pass

            r.set_data(body)
            r.mimetype = "application/json"
    except Exception:
        pass
    return r

# ---- Admin: upload files into corpus (.txt/.md/.jsonl) ----
import os, json, datetime
from flask import request, jsonify
BASE_DIR="/home/kmages"
UPLOAD_DIR=f"{BASE_DIR}/backend/uploads"
GOLDEN=f"{BASE_DIR}/golden.jsonl"
def _now_iso(): return datetime.datetime.now().isoformat(timespec="seconds")
def _append_golden(title, text, meta):
    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    with open(GOLDEN,"a",encoding="utf-8") as f:
        f.write(json.dumps({"title":title,"text":text,"meta":meta,"date":_now_iso()}, ensure_ascii=False)+"\n")

@app.route("/admin/api/upload", methods=["POST"])
def admin_api_upload():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    files = request.files.getlist("file") or []
    added=0; skipped=0
    for f in files:
        try:
            name = os.path.basename(f.filename or "").strip()
            if not name: skipped += 1; continue
            ext = name.lower().rsplit(".",1)[-1] if "." in name else ""
            data = f.read()
            text = data.decode("utf-8", errors="ignore")
            # Save a copy
            with open(os.path.join(UPLOAD_DIR, name), "wb") as out:
                out.write(data)
            if ext == "jsonl":
                for ln in text.splitlines():
                    ln = ln.strip()
                    if not ln: continue
                    try:
                        j = json.loads(ln)
                        _append_golden(j.get("title") or name, j.get("text") or j.get("content") or ln, {"source":"admin_upload","file":name})
                        added += 1
                    except Exception:
                        _append_golden(name, ln, {"source":"admin_upload_raw","file":name})
                        added += 1
            else:
                _append_golden(name, text, {"source":"admin_upload","file":name})
                added += 1
        except Exception:
            skipped += 1
    return jsonify({"ok": True, "added": added, "skipped": skipped, "golden": GOLDEN, "uploads": UPLOAD_DIR})

