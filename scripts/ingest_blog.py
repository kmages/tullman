#!/usr/bin/env python3
import argparse, hashlib, json, re, sys
from datetime import datetime
from pathlib import Path
import feedparser
from bs4 import BeautifulSoup

BASE = Path.home() / "tullman"
OUT  = BASE / "data" / "content" / "content.jsonl"
TAG  = "tullman_blog"

def sha(s:str)->str: return hashlib.sha256(s.encode("utf-8","ignore")).hexdigest()

def strip_html(html:str)->str:
    soup=BeautifulSoup(html or "","lxml")
    for t in soup(["script","style","noscript"]): t.decompose()
    return soup.get_text("\n", strip=True)

def chunk(text:str, max_chars=1200, overlap=120):
    text=re.sub(r"\r\n?", "\n", text)
    text=re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text: return []
    paras=[p.strip() for p in text.split("\n\n") if p.strip()]
    cur=[]; cur_len=0; out=[]
    for p in paras:
        add=(2 if cur else 0)+len(p)
        if cur_len+add<=max_chars or not cur: cur.append(p); cur_len+=add
        else:
            out.append("\n\n".join(cur))
            tail=out[-1][-overlap:] if overlap and out[-1] else ""
            cur=[tail,p] if tail else [p]; cur_len=len(tail)+2+len(p) if tail else len(p)
    if cur: out.append("\n\n".join(cur))
    return out

def load_seen(path:Path):
    seen=set()
    if path.exists():
        with open(path,"r",encoding="utf-8") as f:
            for line in f:
                try:
                    j=json.loads(line); h=j.get("hash")
                    if h: seen.add(h)
                except: pass
    return seen

def fetch_page(start_index:int, page_size:int)->feedparser.FeedParserDict:
    feed=f"https://tullman.blogspot.com/feeds/posts/default?alt=atom&start-index={start_index}&max-results={page_size}"
    return feedparser.parse(feed)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--page-size", type=int, default=500)
    ap.add_argument("--max-pages", type=int, default=50) # enough for full history
    args=ap.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen=load_seen(OUT)

    new=0; total=0
    with open(OUT,"a",encoding="utf-8") as out:
        for page in range(args.max_pages):
            start=page*args.page_size+1
            d=fetch_page(start,args.page_size)
            entries=d.entries or []
            if not entries: break
            for e in entries:
                total+=1
                url     = e.link
                title   = e.title
                updated = getattr(e, "updated", "")
                published = getattr(e, "published", "")
                html    = (e.get("content",[{}])[0].get("value")
                           or e.get("summary","") or "")
                text    = strip_html(html)
                for i,ck in enumerate(chunk(text), start=1):
                    h=sha(f"{url}::chunk::{i}::{ck[:400]}")
                    if h in seen: continue
                    seen.add(h)
                    out.write(json.dumps({
                        "id": h,
                        "title": f"{title} chunk {i}",
                        "source_path": url,        # canonical URL
                        "source_name": title,
                        "source_type": "blog",
                        "published": published,
                        "updated": updated,
                        "part": f"chunk_{i}",
                        "text": ck,
                        "url": url,                # public can cite this
                        "tags": ["tullman_ai", TAG],
                        "hash": h
                    }, ensure_ascii=False)+"\n")
                    new+=1
            if len(entries) < args.page_size:
                break
    print(f"[blog] scanned {total} posts, added {new} chunks -> {OUT}")
if __name__=="__main__":
    main()
