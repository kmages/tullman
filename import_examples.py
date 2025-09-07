#!/usr/bin/env python3
import os, re, json, requests

P = os.path.expanduser('~/tullman/paste_qas.txt')
txt = open(P, 'r', encoding='utf-8', errors='ignore').read()

# Normalize weird quotes; strip markdown prefixes (**,* , >) at line start
lines = []
for ln in txt.splitlines():
    ln = ln.replace('\u2019', "'").replace('\u2014','—').replace('\u2013','-')
    ln = re.sub(r'^\s*(\*\*|\*|>)\s*', '', ln)
    lines.append(ln.rstrip())

q = None
a = []
pairs = []

def flush():
    global q, a, pairs
    if not q: 
        a.clear(); return
    ans = ''.join(a).strip()
    if ans:
        # denylist: skip 9/11
        if '9/11' in q or '9-11' in q or ('Twin Towers' in ans and '2 blocks' in ans):
            pass
        else:
            pairs.append((q.strip(), ans))
    q = None; a.clear()

for ln in lines:
    low = ln.lower()
    if low.startswith('q:') or low.startswith('question:'):
        flush()
        q = ln.split(':',1)[1].strip()
        a = []
    elif low.startswith('a:') or low.startswith('answer:'):
        a = [ln.split(':',1)[1].lstrip()]
    else:
        if a is not None and q is not None:
            a.append('\n' + ln)

flush()

# De-dup by question (last wins)
seen = {}
for qq, aa in pairs:
    seen[qq] = aa

created = updated = failed = 0
for qq, aa in seen.items():
    payload = {"primary_question": qq, "answer": aa, "aliases": [], "active": True, "locked": True}
    try:
        r = requests.post("http://localhost:5057/api/examples", json=payload, timeout=30)
        if r.status_code == 201:
            created += 1
        elif r.status_code in (200, 409):
            updated += 1
        else:
            failed += 1
    except Exception:
        failed += 1

print(json.dumps({
    "parsed_pairs": len(pairs),
    "unique_upserts": len(seen),
    "created": created,
    "updated": updated,
    "failed": failed
}))
