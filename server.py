#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, json, uuid, logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from collections import deque, OrderedDict
from fastapi.responses import FileResponse
from fastapi import UploadFile, File
from app.tuning import router as tune_router

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# --------- Config ---------
BASE = Path.home() / "tullman"
CONTENT = BASE / "data" / "content" / "content.jsonl"

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

VOICEPRINT = (
    "You are Howard Tullman. Write in first person (I, my). "
    "No greetings. The FIRST sentence must directly answer the question. "
    "If the question implies an audience (e.g., a 10-year-old), match that level. "
    "Use prior context and the JSON WEAVE only if they improve accuracy—otherwise ignore them. "
    "Be direct, practical, operator-minded. Prefer 'founded and ran' (never 'founded or ran'). "
    "If you cite, use short chips (Title - URL). Return clean Markdown."
)

SAFE_CHIP_DOMAINS = (
    "howardtullman.com","tullman.blogspot.com","blogspot.com",
    "inc.com","northwestern.edu","wikipedia.org"
)

# --------- App + logger ---------
app = FastAPI(title="Tullman.ai")
log = logging.getLogger("tullman")
logging.basicConfig(level=logging.INFO)

# --------- Schemas ---------
class ChatRequest(BaseModel):
    prompt: str
    public: bool = True
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: List[Dict[str,str]] = []

# --------- Session store ---------
SESSIONS: "OrderedDict[str, deque[Tuple[str,str]]]" = OrderedDict()
MAX_TURNS = 16
MAX_SESS  = 200
def get_session(sid: Optional[str]) -> Tuple[str, deque]:
    sid = sid or uuid.uuid4().hex
    hist = SESSIONS.get(sid)
    if hist is None:
        hist = deque(maxlen=MAX_TURNS); SESSIONS[sid]=hist
        if len(SESSIONS)>MAX_SESS: SESSIONS.popitem(last=False)
    else:
        SESSIONS.move_to_end(sid)
    return sid, hist

# --------- JSONL retriever ---------
_ROWS: Optional[List[Dict]] = None
def load_rows(limit:int=20000)->List[Dict]:
    global _ROWS
    if _ROWS is not None: return _ROWS
    rows=[]
    if CONTENT.exists():
        with CONTENT.open("r", encoding="utf-8") as f:
            for i,line in enumerate(f):
                t=line.strip()
                if not t: continue
                try: rows.append(json.loads(t))
                except: pass
                if i>=limit: break
    _ROWS=rows; log.info("jsonl rows=%d (%s)", len(rows), CONTENT)
    return _ROWS

def _score(q: str, text: str)->int:
    ql=(q or "").lower(); tl=(text or "").lower()
    if not tl: return 0
    terms=set(re.findall(r"[a-z0-9]{4,}", ql))
    return sum(tl.count(t) for t in terms)

def weave_from_json(prompt:str,k:int=6,max_chars:int=1800)->Tuple[str,List[Dict]]:
    rows=load_rows(); scored=[]
    for r in rows:
        t=r.get("text") or ""
        s=_score(prompt,t)
        if s>0: scored.append((s,r))
    scored.sort(key=lambda x:x[0], reverse=True)
    parts=[]; links=[]; total=0
    for _,r in scored[:k]:
        txt=(r.get("text") or "").strip()
        if not txt: continue
        snip=re.sub(r"\s+"," ",txt)[:400]
        parts.append(f"- {snip}")
        u=(r.get("url") or "").strip()
        if u:
            title=(r.get("title") or r.get("source_name") or u).strip()
            links.append({"title":title,"url":u})
        total += len(snip)
        if total>=max_chars: break
    return "\n".join(parts), links[:4]

# --------- OpenAI draft (with fallbacks) ---------
def call_gpt(prompt:str, prior:str, weave:str, links:List[Dict])->str:
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        models = [OPENAI_MODEL] if OPENAI_MODEL else []
        models += ["gpt-5-thinking","gpt-4o","gpt-4o-mini"]
        link_md = "\n".join(f"- {l.get('title','').strip()}: {l.get('url','').strip()}"
                            for l in (links or []) if l.get("url"))
        sysmsg = VOICEPRINT
        user = ("PRIOR_CONTEXT:\n" + (prior or "(none)")
                + "\n\nPROMPT:\n" + (prompt or "")
                + ("\n\nWEAVE:\n"+weave if weave else "")
                + ("\n\nLINKS:\n"+link_md if link_md else ""))
        last=None
        for m in models:
            try:
                log.info("gpt model=%s", m)
                resp = openai.ChatCompletion.create(
                    model=m,
                    messages=[{"role":"system","content":sysmsg},
                              {"role":"user","content":user}],
                    temperature=0.2,
                )
                text=(resp["choices"][0]["message"]["content"] or "").strip()
                if text: return text
            except Exception as e:
                last=e; log.warning("gpt fail %s: %s", m, e.__class__.__name__)
        if last: log.error("gpt unavailable: %s", last.__class__.__name__)
    except Exception as e:
        log.error("gpt import/call error: %s", e.__class__.__name__)
    return ""  # failure

# --------- Kenifier (no-op placeholder) ---------
def kenify_markdown(prompt:str, md:str, sources:List[Dict])->str:
    return md

# --------- Finalizer & chips ---------
def strip_greeting(text:str)->str:
    if not isinstance(text,str): return text
    t=text.lstrip(); low=t.lower()
    if not low.startswith("hi") or "howard t" not in low[:80]: return text
    i=low.find("howard t"); j=i+len("howard tullman") if i!=-1 else 0
    k=j
    while 0<=k<len(t) and (t[k] in ".! " or ord(t[k]) in (45,8211,8212)): k+=1
    return t[k:].lstrip()

def filter_chips(prompt:str, links:List[Dict], max_links:int=2)->List[Dict]:
    out=[]; seen=set()
    for l in links or []:
        u=(l.get("url") or "").strip().lower()
        if not u: continue
        host=re.sub(r"^https?://","",u).split("/")[0].lower()
        if not any(host.endswith(d) for d in SAFE_CHIP_DOMAINS): continue
        title=(l.get("title") or u).strip()
        if u in seen: continue
        seen.add(u); out.append({"title":title,"url":u})
        if len(out)>=max_links: break
    return out

def finalize(prompt:str, md:str, links:List[Dict])->Tuple[str,List[Dict]]:
    t=(md or "").strip()
    t=strip_greeting(t).replace("founded or ran","founded and ran")
    t=re.sub(r"[ \t]+"," ",t); t=re.sub(r"\n{3,}","\n\n",t)
    return t, filter_chips(prompt, links or [], max_links=2)

# --------- Pipeline ---------
def pipeline(prompt:str, prior:str)->Tuple[str,List[Dict]]:
    weave, links = weave_from_json(prompt)
    draft = call_gpt(prompt, prior, weave, links)
    if not draft:
        return ("I’m having trouble generating a response right now — please try again.", [] )
    md = kenify_markdown(prompt, draft, links)
    return finalize(prompt, md, links)

# --------- Routes ---------
@app.get("/health")
def health():
    rows=load_rows(); counts={}
    for r in rows:
        t=r.get("source_type") or "unknown"
        counts[t]=counts.get(t,0)+1
    return JSONResponse({"ok":True,"total":sum(counts.values()),"counts":counts})

@app.post("/chat")
def chat(req: ChatRequest):
    q=(req.prompt or "").strip()
    sid, hist = get_session(req.session_id)
    if not q:
        return JSONResponse(ChatResponse(answer="Ask a question first.", session_id=sid, sources=[]).dict())
    prior = " ".join(f"{r}: {c}" for r,c in list(hist)[-8:])
    try:
        md, links = pipeline(q, prior)
    except Exception:
        log.exception("chat_error")
        return JSONResponse(ChatResponse(answer="Sorry - server error. Please try again.", session_id=sid, sources=[]).dict())
    hist.append(("user", q)); hist.append(("assistant", md))
    return JSONResponse(ChatResponse(answer=md, session_id=sid, sources=links).dict())

@app.get("/")
def root():
    return JSONResponse({"ok":True,"msg":"Tullman.ai API up"})

CFG_DIR = BASE / "config"; CFG_DIR.mkdir(parents=True, exist_ok=True)
VOICE_FILE = CFG_DIR / "voiceprint.txt"
UPLOAD_DIR = BASE / "in" / "uploads"; UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def load_voiceprint_default() -> str:
    try:
        if VOICE_FILE.exists(): return VOICE_FILE.read_text(encoding="utf-8")
    except Exception: pass
    return VOICEPRINT

def save_voiceprint(txt: str) -> None:
    VOICE_FILE.write_text(txt, encoding="utf-8")

def apply_voiceprint(txt: str):
    global VOICEPRINT
    VOICEPRINT = txt

class VoiceBody(BaseModel):
    voiceprint: str

@app.get("/admin")
def admin_page():
    html = BASE / "frontend" / "admin.html"
    return FileResponse(str(html)) if html.exists() else JSONResponse({"ok": False, "msg": "Put admin.html in ~/tullman/frontend/"}, status_code=404)

@app.get("/admin/voiceprint")
def get_voiceprint():
    return JSONResponse({"voiceprint": load_voiceprint_default()})

@app.put("/admin/voiceprint")
def set_voiceprint(body: VoiceBody):
    vp=(body.voiceprint or "").strip()
    save_voiceprint(vp); apply_voiceprint(vp)
    return JSONResponse({"ok": True})

@app.post("/admin/upload")
async def upload_files(file: list[UploadFile] = File(...)):
    saved=[]
    for f in file:
        dest = UPLOAD_DIR / f.filename
        with open(dest, "wb") as out:
            out.write(await f.read())
        saved.append(str(dest))
    return JSONResponse({"ok": True, "saved": saved})

@app.post("/admin/ingest")
def ingest_now():
    import subprocess, shlex
    cmd = f"/home/kmages/tullman/venv/bin/python /home/kmages/tullman/scripts/ingest_any.py --inputs {UPLOAD_DIR}"
    subprocess.Popen(shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return JSONResponse({"ok": True, "msg": "Ingest started"})


# === strict chip filter (Howard-only + relevance) ===
def _filter_chips_strict(prompt: str, links, max_links: int = 2):
    import re
    allow = ("howardtullman.com","tullman.blogspot.com","blogspot.com",
             "inc.com","northwestern.edu","wikipedia.org")
    q = (prompt or "").lower()
    # long-ish tokens only
    toks = [t for t in re.findall(r"[a-z0-9]{4,}", q)]
    out, seen = [], set()
    for l in links or []:
        u = (l.get("url") or "").strip()
        if not u: 
            continue
        host = re.sub(r"^https?://","",u).split("/")[0].lower()
        if not any(host.endswith(d) for d in allow):
            continue
        title = (l.get("title") or u).strip().lower()
        # simple relevance: title must share at least one token with the prompt
        if toks and not any(t in title for t in toks):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append({"title": l.get("title") or u, "url": u})
        if len(out) >= max_links:
            break
    return out

# install as default
try:
    filter_chips = _filter_chips_strict  # type: ignore
except Exception:
    pass

app.include_router(tune_router)
