import re
import json
from pathlib import Path
# ASCII-only: JSON → GPT-5 (Howard) → Kenifier
import os, json, re, logging
_log = logging.getLogger("howard")

BASE     = Path.home() / "tullman"
CONTENT  = BASE / "data" / "content" / "content.jsonl"

VOICEPRINT = (
"You are Howard Tullman. Write in first person (I, my). No greetings. The FIRST sentence must directly answer the question. If the question implies an audience (e.g., a 10-year-old), match that level. Use prior context and JSON WEAVE only if they improve accuracy and clarity—otherwise ignore them. Be direct, practical, operator-minded. Prefer \"founded and ran\" (never \"founded or ran\"). If you cite, use short chips (Title - URL). Return clean Markdown."
)

_cache = None
def _load_rows(limit=20000):
    global _cache
    if _cache is not None:
        return _cache
    rows = []
    if CONTENT.exists():
        with CONTENT.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except:
                    pass
                if i >= limit:
                    break
    _cache = rows
    _log.info("howard.jsonl rows=%d", len(rows))
    return _cache

def _score(q, text):
    ql = (q or "").lower()
    tl = (text or "").lower()
    if not tl:
        return 0
    terms = set(re.findall(r"[a-z0-9]{4,}", ql))
    return sum(tl.count(t) for t in terms)

def weave_from_json(prompt, k=6, max_chars=1800):
    rows = _load_rows()
    scored = []
    for r in rows:
        t = r.get("text") or ""
        s = _score(prompt, t)
        if s > 0:
            scored.append((s, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    parts, links = [], []
    total = 0
    for _, r in scored[:k]:
        txt = (r.get("text") or "").strip()
        if not txt:
            continue
        snip = re.sub(r"\s+", " ", txt)[:400]
        parts.append(f"- {snip}")
        u = (r.get("url") or "").strip()
        if u:
            title = (r.get("title") or r.get("source_name") or u).strip()
            links.append({"title": title, "url": u})
        total += len(snip)
        if total >= max_chars:
            break
    return "\n".join(parts), links[:4]

def _gpt(prompt, prior, weave, links):
    try:
        import openai
        openai.api_key = os.environ.get("OPENAI_API_KEY", "")
        models = []
        envm = os.environ.get("OPENAI_MODEL", "").strip()
        if envm:
            models.append(envm)
        models += ["gpt-5-thinking", "gpt-4o", "gpt-4o-mini"]

        link_md = "\n".join(f"- {l['title']}: {l['url']}" for l in (links or []) if l.get("url"))
        sysmsg = VOICEPRINT
        user = (
            "PRIOR_CONTEXT:\n" + (prior or "(none)")
            + "\n\nPROMPT:\n" + (prompt or "")
            + ("\n\nWEAVE:\n" + weave if weave else "")
            + ("\n\nLINKS:\n" + link_md if link_md else "")
        )
        for m in models:
            try:
                _log.info("howard.gpt model=%s", m)
                resp = openai.ChatCompletion.create(
                    model=m,
                    messages=[{"role": "system", "content": sysmsg},
                              {"role": "user",   "content": user}],
                    temperature=0.2,
                )
                text = (resp["choices"][0]["message"]["content"] or "").strip()
                if text:
                    return text
            except Exception as e:
                _log.warning("howard.gpt fail %s: %s", m, e.__class__.__name__)
    except Exception as e:
        _log.warning("howard.gpt unavailable: %s", e.__class__.__name__)
    return ""

def _kenify(prompt, md, sources):
    """
    Try a lightweight kenifier without importing server to avoid circular imports.
    If none is available, return md unchanged.
    """
    try:
        # If you have a kenifier in composer, prefer that
        from app.composer import kenify_markdown as _k
        return _k(prompt, md, sources)
    except Exception:
        return md

def answer(prompt: str, prior: str):
    weave, links = weave_from_json(prompt)
    draft = _gpt(prompt, prior, weave, links) or ""
    if not draft:
        # transparent failure (no biased fallback content)
        return "I’m having trouble generating a response right now — please try again.", []
    md = _kenify(prompt, draft, links)
    # keep only Howard/Inc/Northwestern/Wikipedia chips
    safe = ("howardtullman.com","tullman.blogspot.com","blogspot.com","inc.com","northwestern.edu","wikipedia.org")
    links = [l for l in (links or []) if any((l.get("url") or "").lower().endswith(d) for d in safe)]
    return md, links


def _one_liner(prompt: str) -> str:
    q=(prompt or "").lower()
    def has(*ks): return any(k in q for k in ks)
    # Kendall
    if 'kendall' in q: 
        return ("At Kendall College I focused on execution and employability: modern Goose Island facilities, "
                "culinary/hospitality focus, employer partnerships and real projects, and operating discipline with "
                "clear, measurable outcomes.")
    # Reflective / personal
    if has('define success','success'):
        return "Success is sustained impact: useful outcomes shipped on time, with integrity, that compound over years."
    if has('chasing goals','forget when chasing'):
        return "People forget the baseline and the cost — without a baseline you can’t prove progress; without a cost you won’t focus."
    if has('kindness'):
        return "Kindness compounds: it lowers friction, increases trust, and keeps teams resilient when things break."
    if has('afterlife'):
        return "I believe in legacy here: what we build, the people we grow, and the work that outlasts us."
    if has('free will'):
        return "We have agency inside constraints; choices compound and become character."
    if has('fear of death','fear death'):
        return "We fear loss of control; the antidote is purpose — ship work that matters while you have the time."
    if has('advice','younger self'):
        return "Start sooner. Ship smaller. Measure honestly. Choose your people carefully — they set your ceiling."
    if has('true love','chemistry'):
        return "It’s chemistry that becomes commitment: shared values, useful habits, and showing up when it’s not fun."
    if has('irrational'):
        return "I over-index on teams that keep promises; it’s irrational until the returns show up."
    if has('misunderstand','misunderstood'):
        return "I’m direct because time matters; it’s respect for outcomes and people, not cynicism."
    if has('stay grounded','grounded'):
        return "Ship something real every week; momentum beats mood."
    if has('secret fuel'):
        return "Momentum — small wins, visible metrics, and teams who keep promises."
    if has('unshakable'):
        return "Execution beats theater."
    if has('core trait'):
        return "I’m an operator: I turn ideas into outcomes."
    if has('cost of being misunderstood','cost'):
        return "You trade popularity for clarity; it’s worth it if impact is the goal."
    if has('need to hear'):
        return "You’re closer than you think — cut the scope, ship the first version, and measure truthfully."
    if has('solitude'):
        return "It’s where I hear myself think; strategy needs quiet."
    if has('what scares you most about ai','scares you most about ai'):
        return "Complacency scares me — leaders who pause while competitors compound advantage with AI."
    if has('climate'):
        return "Climate risk is compounding; the only sane move is to instrument reality and act on the numbers."
    # Default (still question-first, on-voice)
    return "Here’s my view in one sentence, then a short, useful rationale."

