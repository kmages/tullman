from flask import request, jsonify
import os, re, json
from pathlib import Path

# ---------- files ----------
SEED       = "/home/kmages/backend/voiceprint_seed.jsonl"
VOICE_STG  = "/home/kmages/backend/voiceprint_staging.txt"
VOICE_PROD = "/home/kmages/backend/voiceprint_prod.txt"

# ---------- guard (rabbi rule) ----------
BLOCK = re.compile(r"(free\s*-?\s*will|religion(s|al)?|faith|\bgod(s)?\b|deity|meaning\s+of\s+life|purpose\s+of\s+life|afterlife|heaven|hell|death|dying|mortality|philosoph(y|ical|er))", re.I)
FIXED = "I am not a rabbi, priest or philosopher and I’m also in a hurry so questions like this are not a good use of my time or yours."

# ---------- examples ----------
STOP=set("a an and are as at be but by for from had has have i if in is it its of on or our so than that the their then there these they this to under was were what when where which who why will with you your".split())
WORD=re.compile(r"[a-z0-9]+")
def _tok(x): return {t for t in WORD.findall((x or "").lower()) if len(t)>2 and t not in STOP}

def _seed_pairs():
    out=[]
    try:
        with open(SEED,"r",encoding="utf-8") as f:
            for ln in f:
                ln=ln.strip()
                if not ln: continue
                try:
                    j=json.loads(ln)
                    q=(j.get("prompt") or "").strip()
                    a=(j.get("response") or "").strip()
                    if q and a: out.append((q,a))
                except: pass
    except: pass
    return out

def _best_match(q):
    tq=_tok(q)
    if not tq: return None
    best=None; sc=0.0
    for pq,pa in _seed_pairs():
        tp=_tok(pq)
        if not tp: continue
        jac=len(tq & tp)/max(1, len(tq|tp))
        if "kendall" in tq and "kendall" in tp: jac += 0.25
        if jac>sc: sc=jac; best=pa
    return (best, sc) if sc>=0.42 else (None, sc)

# ---------- identity / topic (for CONTEXT, not final) ----------
def _ident(pl:str):
    if re.search(r"\bwho\s+is\s+howard\s+tullman\??", pl):
        return "I’m a serial entrepreneur, investor, and educator. I’ve led multiple tech companies, ran 1871 in Chicago, and spent decades building teams, backing founders, and writing about execution."
    if re.search(r"\bwhy\b.*\bai\s+strategy\b|\bwhy\s+do\s+i\s+need\s+an\s+ai\s+strategy\??", pl):
        return "Because it drives results: faster execution, lower cost, and clear differentiation. Start with a 12-month roadmap, pick 2–3 high-value use cases, ship a small win in 30–60 days, then scale what works."
    if re.search(r"\b(kendall)\b.*(changed|change|under\s+your\s+leadership)", pl):
        return "At Kendall I focused on speed, relevance, and outcomes—tighter industry ties, more real-world projects, measurable results, and higher expectations for students, faculty, and partners."
    if re.search(r"\b(relativity|einstein)\b.*\b(ten|10|child|kid|kids|student)\b|\bteach\b.*\brelativity\b", pl):
        return "Imagine you’re on a very fast train. You toss a ball; to you it looks normal, but to someone outside it moves differently. Relativity says time and distance can look different depending on speed and gravity. Go faster or be near something heavy, and clocks tick a little differently. That’s it: motion and gravity change what we see as time and space."
    return None

# ---------- rule-of-thumb while GPT is down ----------
def _lifespan_stub(pl:str):
    if re.search(r"\b(how\s+long\s+(do|does)\s+dogs?\s+live|dog\s+lifespan|life\s*span\s+of\s+dogs?)\b", pl):
        return "Most dogs live about 10–13 years. Smaller breeds often reach 12–16; giant breeds are closer to 7–10. Care, genetics, and size drive the spread."
    if re.search(r"\b(how\s+long\s+(do|does)\s+cats?\s+live|cat\s+lifespan|life\s*span\s+of\s+cats?)\b", pl):
        return "Indoor cats often reach 12–15 years and many live past 16; outdoor cats trend shorter. Care and genetics matter."
    if re.search(r"\b(how\s+long\s+(do|does)\s+humans?\s+live|life\s+expectancy)\b", pl):
        return "In the U.S., life expectancy is roughly mid-70s to low-80s depending on sex and region. Health, lifestyle, and access drive the spread."
    return None

# ---------- GPT helpers ----------
_client=None
def _voiceprint():
    for p in (VOICE_STG, VOICE_PROD):
        try:
            t=Path(p).read_text(encoding="utf-8").strip()
            if t: return t
        except: pass
    return ("SYSTEM: Rewrite answers in Howard Tullman’s voice.\n"
            "Tone: first person; direct; concise; no fluff; no hedging.\n"
            "Output: one concise first-person answer only.")

def _gpt_weave(prompt:str, context:str|None):
    """Always call GPT to create the final answer; weave context if present."""
    global _client
    try:
        from openai import OpenAI
    except Exception as _e:
            fb = "Give me one detail (timeframe, scope, or result) and I’ll answer directly."
            try:
                return jsonify({"answer": fb, "response": fb, "ruled": False, "service": service_tag})
            except Exception:
                from flask import Response
                return Response("{\"answer\":\"%s\",\"response\":\"%s\",\"ruled\":false,\"service\":\"%s\"}" % (fb, fb, service_tag), mimetype="application/json")
    try:
        if _client is None: _client = OpenAI()
        model = os.getenv("OPENAI_MODEL","gpt-4o-mini")  # set to gpt-5 if available
        sys = _voiceprint()
        parts=[]
        if context:
            parts.append(f"Reference to weave:\n{context}")
        parts.append(f"Prompt:\n{prompt}")
        
parts.append("Write in first person as Howard. Use a short, clean paragraph (3–5 sentences). Start with ‘I …’. No markdown headings.")
        
        
user_msg="\n\n".join(parts)
        r = _client.chat.completions.create(
            model=model, temperature=0.35,
            messages=[{"role":"system","content":sys},
                      {"role":"user","content":user_msg}],
        )
        txt = (r.choices[0].message.content or "").strip()
        
try:
            return txt or None
        except Exception:
            return txt or None
    except Exception:
        return None

# ---------- register hotfix ----------

# --- post-process to keep answers tight and list-free ---
def _polish(t):
    import re
    t = re.sub(r"^s*d+[.)]s*", "", t, flags=re.M)   # remove 1. 2) etc.
    t = re.sub(r"^s*[-*•]s*", "", t, flags=re.M)      # remove bullets
    t = re.sub(r"
+", " ", t)                          # collapse newlines
    t = re.sub(r"s{2,}", " ", t).strip()               # collapse spaces
    return t


def _i_voice(t):
    import re
    s = t or ""
    # Openers like "Chicago is..." → "I love Chicago because it is..."
    s = re.sub(r"^s*Chicagos+is","I love Chicago because it is", s, flags=re.I)
    # Rewrite bullets (1., -, *, •) to I-voice
    def _fix_bullet(line):
        core = re.sub(r"^s*(?:d+.s*|[-*•]s*)","", line)
        core = re.sub(r"^s***(.*?)**s*:s*","", core)           # drop bold heading
        core = re.sub(r"^s*(The|the)s+city","I love the city", core)
        core = re.sub(r"^s*Chicago","I love Chicago", core)
        if not re.match(r"s*[Ii]", core):
            core = "I " + (core[:1].lower() + core[1:]) if core else "I value it."
        return "- " + core.strip()
    s = re.sub(r"^s*(?:d+.s*|[-*•]s*).* ,
               lambda m: _fix_bullet(m.group(0))
        parts.append("If you use bullets, each bullet MUST begin with one of: I love, I value, I use, I rely on, I enjoy, I care about, I’m proud. Do NOT start bullets with: I is, I known, Chicago is, The city is. No markdown headings."),
               s, flags=re.M)
    # Collapse crazy spacing but keep bullets per line
    s = re.sub(r"[ 	]{2,}"," ", s).strip()
    return s

def install(app, service_tag):
    @app.before_request
    def _intercept():
        try:
            if request.path!="/retrieve" or request.method!="POST":
                return None
            data = request.get_json(silent=True) or {}
            prompt = (data.get("prompt") or data.get("q") or data.get("text") or "").strip()

            # 0) guard
            if BLOCK.search(prompt or ""):
                return jsonify({"answer":FIXED,"response":FIXED,"ruled":True,"service":service_tag})

            pl=(prompt or "").lower()

            # 1) build context (identity > example)
            ctx = _ident(pl)
            if not ctx:
                ex,score = _best_match(prompt)
                if ex: ctx = f"Example answer:\n{ex}"

            # 2) ALWAYS GPT (weave context into answer)
            ans = _gpt_weave(prompt, ctx)

            # 3) safe fallback chain if GPT unavailable
            if not ans:
                ans = ctx or _lifespan_stub(pl)
            if not ans:
                ans = "Give me one detail (timeframe, scope, or result) and I’ll answer directly."

            return jsonify({"answer": ans,"response":ans,"ruled":False,"service":service_tag})
        except Exception:
            return None
