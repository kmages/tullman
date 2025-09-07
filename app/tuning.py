from fastapi import APIRouter, Body
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional, Dict
import json, time, uuid, os

router = APIRouter(prefix="/admin/tune", tags=["tune"])

BASE = Path.home() / "tullman"
CFG  = BASE / "config"; CFG.mkdir(parents=True, exist_ok=True)
RULES_FILE = CFG / "style_rules.json"
CORR_FILE  = CFG / "corrections.jsonl"
CANON_FILE = CFG / "canon.jsonl"
CONTENT_JSONL = BASE / "data" / "content" / "content.jsonl"

def _read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write_json(path: Path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def load_rules() -> List[str]:
    return _read_json(RULES_FILE, [])

def save_rules(rules: List[str]) -> None:
    _write_json(RULES_FILE, rules)

class Feedback(BaseModel):
    prompt: str
    draft: str
    decision: str                     # "ok" | "rewrite" | "not_me"
    edited: Optional[str] = None      # Howard’s corrected phrasing
    add_rules: List[str] = []         # short style deltas ("avoid X", "prefer Y")
    session_id: Optional[str] = None

@router.get("/rules")
def get_rules():
    return {"rules": load_rules()}

@router.put("/rules")
def put_rules(payload: Dict):
    rules = list(map(str, payload.get("rules", [])))
    save_rules(rules)
    return {"ok": True, "count": len(rules)}

@router.post("/feedback")
def post_feedback(fb: Feedback):
    # 1) Log correction
    rec = fb.dict()
    rec["ts"] = int(time.time())
    with CORR_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 2) Merge rules
    if fb.add_rules:
        cur = load_rules()
        merged = cur[:]
        for r in fb.add_rules:
            r = r.strip()
            if r and r not in merged:
                merged.append(r)
        save_rules(merged)

    # 3) Return a final string to show in the UI (prefer Howard’s edit if given)
    final = (fb.edited or fb.draft or "").strip()
    return {"ok": True, "final": final}

# ---- Quick indexing (text → content.jsonl immediately)
class IndexText(BaseModel):
    title: str
    text: str
    tags: List[str] = []

@router.post("/index-text")
def index_text(it: IndexText):
    row = {
        "id": str(uuid.uuid4()),
        "title": it.title.strip() or "admin: text",
        "source_path": str(BASE / "in" / "uploads"),
        "source_name": "admin",
        "source_type": "txt",
        "part": "chunk_1",
        "text": it.text,
        "tags": ["tullman_ai", "admin"] + list(dict.fromkeys(it.tags)),
        "hash": str(uuid.uuid4()).replace("-", "")
    }
    CONTENT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with CONTENT_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "added": 1}
