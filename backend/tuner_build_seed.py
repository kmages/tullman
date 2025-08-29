#!/usr/bin/env python3
# /home/kmages/backend/tuner_build_seed.py
import json, os, re, datetime
from collections import Counter

GOLDEN = "/home/kmages/golden.jsonl"
SEED_OUT = "/home/kmages/backend/voiceprint_seed.jsonl"
PROMPT_OUT = "/home/kmages/backend/kenifier_prompt.txt"

# Defaults
MAX_EXAMPLES = int(os.getenv("TUNER_MAX_EXAMPLES", "20"))

# Common GPT-isms & fluff to suppress
DEFAULT_BANNED = [
    "as an ai", "as a large language model",
    "i cannot", "i can’t", "i am unable", "i’m unable",
    "it depends", "hopefully", "in conclusion",
    "furthermore", "moreover", "additionally",
    "let’s unpack", "delve into", "journey",
    "ultimately", "at the end of the day",
    "on the one hand", "on the other hand",
]

FILLERS = [
    "basically", "actually", "honestly", "frankly", "literally",
    "sort of", "kind of", "i mean", "you know"
]

def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")

def load_golden(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
                rows.append(obj)
            except Exception:
                pass
    return rows

def select_recent_edits(rows, max_n):
    # Keep only Howard-edited responses
    edits = [r for r in rows if (r.get("source") or "").lower().strip()=="howard edit"]
    # Sort newest first
    edits.sort(key=lambda r: r.get("date",""), reverse=True)
    return edits[:max_n]

def heuristic_style(edits):
    # Collect quick signals from edited responses
    texts = [ (e.get("response") or "") for e in edits ]
    joined = "\n".join(texts).lower()

    # Em dash dislike (Ken’s style note)
    ban_em_dash = "—" in joined or "---" in joined

    # Ban phrases present in defaults or heuristic extras
    banned = set(DEFAULT_BANNED)

    # If we see fillers in examples, we *still* ban them for safety
    for tok in FILLERS:
        banned.add(tok)

    # Overlong sentences: suggest brevity
    # Compute rough avg sentence length
    sents = re.split(r"[.!?]\s+", "\n".join(texts))
    avg_len = (sum(len(s.split()) for s in sents if s.strip()) / max(1, len([s for s in sents if s.strip()])))
    prefer_brevity = avg_len > 22  # heuristic threshold

    # N-gram “bitey” signature (very light)
    words = re.findall(r"[A-Za-z']+", joined)
    top_unigrams = [w for w,_ in Counter(words).most_common(50)]

    return {
        "ban_em_dash": ban_em_dash,
        "prefer_brevity": prefer_brevity,
        "banned_phrases": sorted(banned),
        "top_unigrams": top_unigrams,
    }

def write_seed_file(edits, seed_path):
    with open(seed_path, "w", encoding="utf-8") as f:
        for e in edits:
            out = {
                "prompt": e.get("prompt","").strip(),
                "response": e.get("response","").strip(),
                "date": e.get("date") or now_iso(),
                "source": "Howard edit"
            }
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

def make_prompt(edits, style, out_path):
    # Build a compact instruction block Kenifier Lite will inject
    header = [
        "SYSTEM: Rewrite the assistant’s answer in Howard’s concise voice.",
        "Tone rules:",
        "- Direct, grounded, no fluff.",
        "- If you can cut a word, cut it.",
        "- No hedging. No 'as an AI'. No disclaimers.",
        "- Prefer short sentences. Make it punchy.",
    ]
    if style["ban_em_dash"]:
        header.append("- Never use em dashes.")
    if style["prefer_brevity"]:
        header.append("- Tighten long sentences.")
    if style["banned_phrases"]:
        header.append("- Ban these phrases entirely: " + "; ".join(style["banned_phrases"]) + ".")

    examples = ["\nEXAMPLES (latest edits):"]
    for e in edits:
        p = (e.get("prompt") or "").strip()
        r = (e.get("response") or "").strip()
        if not (p and r): 
            continue
        examples.append(f"Q: {p}\nA: {r}\n")

    tail = [
        "Rewrite all output in this voice. Keep factual content; change tone.",
        "Do not explain the rules. Output only the rewritten answer."
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n\n")
        f.write("\n".join(examples) + "\n")
        f.write("\n".join(tail) + "\n")

def main():
    rows = load_golden(GOLDEN)
    edits = select_recent_edits(rows, MAX_EXAMPLES)
    style = heuristic_style(edits)
    os.makedirs(os.path.dirname(SEED_OUT), exist_ok=True)
    write_seed_file(edits, SEED_OUT)
    make_prompt(edits, style, PROMPT_OUT)
    print(f"[tuner] seed: {SEED_OUT}")
    print(f"[tuner] prompt: {PROMPT_OUT}")
    print(f"[tuner] examples: {len(edits)} | ban_em_dash={style['ban_em_dash']} prefer_brevity={style['prefer_brevity']}")

if __name__ == "__main__":
    main()
