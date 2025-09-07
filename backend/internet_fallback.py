#!/usr/bin/env python3
"""
internet_fallback.py (robust)
- Searches multiple Howard sources first, then broad web queries.
- Longer timeouts, more tolerant content length, and multiple DDG selectors.
- Keeps total wall time ~60s (script budgets internally).
"""
import os, sys, json, time, re
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup

# Highest-signal domains first (add/remove freely)
HOWARD_SITES = [
    "howardtullman.com",
    "www.howardtullman.com",
    "inc.com/howard-tullman",
    "www.inc.com/howard-tullman",
    "medium.com/@howardtullman",
    "medium.com/@htullman",
    "www.tullman.com",  # in case legacy links exist
]

UA = {"User-Agent": "Mozilla/5.0 (compatible; TullmanBot/1.0; +https://tullman.ai)"}

def now(): return time.monotonic()

def ddg_search(q, timeout=12):
    """DuckDuckGo html endpoint; returns a list of result URLs."""
    url = "https://duckduckgo.com/html/?" + urlencode({"q": q})
    r = requests.get(url, timeout=timeout, headers=UA)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html5lib")
    links = []
    # try multiple selectors (DDG HTML can vary)
    for sel in ["a.result__a", "a.result__url", "h2 a"]:
        for a in soup.select(sel):
            href = a.get("href")
            if href and href.startswith("http"):
                links.append(href)
    # de-dup keep order
    seen = set(); out = []
    for u in links:
        if u not in seen:
            seen.add(u); out.append(u)
    return out

def fetch_readable(url, timeout=15):
    """Fetch and extract readable text (best-effort)."""
    try:
        r = requests.get(url, timeout=timeout, headers=UA)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html5lib")
        for tag in soup(["script","style","noscript","header","footer","aside","nav"]):
            tag.decompose()
        # Prefer article-ish containers; else fall back to body
        container = soup.find(["article","main","div"], attrs={"class": lambda c: c and any(k in c.lower() for k in [
            "article","content","post","entry","story","main","body","text"])})
        if not container:
            container = soup.body or soup
        chunks = [p.get_text(" ", strip=True) for p in container.find_all(["p","li","blockquote"]) if p.get_text(strip=True)]
        text = " ".join(chunks)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:20000]  # keep prompt size bounded
    except Exception:
        return ""

def build_context(question, hits):
    parts = []
    for h in hits:
        excerpt = h["text"][:1400]
        parts.append(f"SOURCE: {h['url']}\nEXCERPT:\n{excerpt}\n")
    ctx = "\n\n".join(parts)
    return f"QUESTION: {question}\n\n{ctx}".strip()

def openai_weave(question, hits, model="gpt-4o-mini"):
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_APIKEY")
    if not key: return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        ctx = build_context(question, hits)
        messages = [
            {"role":"system","content":(
                "You are Howard Tullman. Answer crisply in his voice. "
                "Weave a relevant quote/anecdote from the supplied sources (if any). "
                "Avoid fluff. Use one subtle inline cite like (source: URL)."
            )},
            {"role":"user","content":(
                "Use these sources if relevant. If none are relevant, answer from first principles in Howard’s voice.\n\n"+ctx
            )},
        ]
        # generous output; script already budgets wall time
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=0.35, max_tokens=900, timeout=55
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return None

def main():
    # Read prompt from stdin JSON or --prompt args
    if len(sys.argv) > 1 and sys.argv[1] == "--prompt":
        prompt = " ".join(sys.argv[2:]).strip()
    else:
        try:
            j = json.loads(sys.stdin.read() or "{}")
        except Exception:
            j = {}
        prompt = (j.get("prompt") or "").strip()

    if not prompt:
        print(json.dumps({"error":"empty prompt"})); return

    t0 = now(); BUDGET = 60.0
    hits = []

    # --- WAVE 1: Howard domains (3 sites max, 3 results each) ---
    for site in HOWARD_SITES:
        if now() - t0 > BUDGET * 0.45: break
        try:
            urls = ddg_search(f"site:{site} {prompt}", timeout=12)[:3]
        except Exception:
            urls = []
        for u in urls:
            if now() - t0 > BUDGET * 0.6: break
            text = fetch_readable(u, timeout=15)
            if len(text) >= 300:   # accept shorter pages than before
                hits.append({"url": u, "text": text})
            if len(hits) >= 3: break
        if len(hits) >= 3: break

    # --- WAVE 2: Broad query variants (first 4 results total) ---
    if now() - t0 <= BUDGET * 0.75 and len(hits) < 2:
        variants = [
            f'site:inc.com/howard-tullman "Howard Tullman" {prompt}',
            f'site:www.inc.com/howard-tullman "Howard Tullman" {prompt}',
            f'"Howard Tullman" {prompt}',
            f'Howard Tullman on {prompt}',
            f'Howard Tullman advice {prompt}',
            f'"Howard Tullman" quote {prompt}',
        ]
        seen = set(h["url"] for h in hits)
        for q in variants:
            if now() - t0 > BUDGET * 0.85 or len(hits) >= 4: break
            try:
                urls = ddg_search(q, timeout=12)[:4]
            except Exception:
                urls = []
            for u in urls:
                if u in seen: continue
                seen.add(u)
                text = fetch_readable(u, timeout=15)
                if len(text) >= 250:
                    hits.append({"url": u, "text": text})
                if now() - t0 > BUDGET * 0.92 or len(hits) >= 4: break

    # --- BUILD ANSWER ---
    # If we have an API key, let GPT weave; else stitch best snippet
    if hits:
        ai = openai_weave(prompt, hits)
        if ai:
            print(json.dumps({"answer": ai, "source":"internet-howard", "sources":[h["url"] for h in hits]}, ensure_ascii=False))
            return
        # stitched fallback w/ inline cite
        best = hits[0]
        snip = best["text"][:800]
        print(json.dumps({"answer": f"{snip} … (source: {best['url']})", "source":"internet-snippet", "sources":[best["url"]]}, ensure_ascii=False))
        return

    # Nothing found in time
    print(json.dumps({"answer":"(no online source found yet)", "source":"internet-none", "sources":[]}, ensure_ascii=False))
if __name__ == "__main__":
    main()
