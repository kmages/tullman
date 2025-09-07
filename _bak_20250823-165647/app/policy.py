# ASCII-only, no smart quotes
ALLOW = (
    "howardtullman.com", "tullman.blogspot.com", "blogspot.com",
    "inc.com", "northwestern.edu", "wikipedia.org"
)
EXCLUDE = ("chunk", "top toady", "roberts")
POLITICAL = ("israel","gaza","hamas","putin","trump","election","politic")
AI_TERMS = ("ai","artificial intelligence","strategy","roadmap","plan","llm","automation","table stakes","table-stakes")

def is_political(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in POLITICAL)

def clean_title(t: str) -> str:
    import re
    if not t: return "Source"
    t = re.sub(r'\s*-\s*chunk\s*\d+\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*chunk\s*\d+\s*$', '', t, flags=re.I).strip()
    return t.title() if t and t.upper()==t else t or "Source"

def filter_links(prompt: str, links: list, max_links=2) -> list:
    import re
    out, seen = [], set()
    q = (prompt or "").lower()
    require_ai = any(k in q for k in ("ai strategy","table stakes","ai roadmap","ai plan"))
    allow_politics = is_political(q)

    for l in links or []:
        u = (l.get("url") or "").strip()
        if not u: 
            continue
        host = re.sub(r"^https?://","",u).split("/")[0].lower()
        if not any(host.endswith(d) for d in ALLOW):
            continue
        title = (l.get("title") or u).strip()
        lt, lu = title.lower(), u.lower()

        if any(x in lt for x in EXCLUDE):
            continue
        if not allow_politics and (is_political(lt) or is_political(lu)):
            continue
        if require_ai and not any(k in (lt+lu) for k in AI_TERMS):
            continue

        key = u.lower()
        if key in seen: 
            continue
        seen.add(key)
        out.append({"title": clean_title(title), "url": u})
        if len(out) >= max_links:
            break
    return out
