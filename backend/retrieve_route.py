
def setup_retrieve(app, db, Example,
                   corpus_dir="/home/kmages/tullman/corpus",
                   golden_path="/var/www/tullman/assets/golden.json",
                   rules_path ="/var/www/tullman/assets/rules.json"):
    """Register /api/retrieve. Pipeline:
       rules (deny/force) -> golden -> corpus -> GPT-internet (Howard) -> openai -> examples -> fallback
       Chips are answered on the front-end from golden.json."""
    from flask import request, jsonify
    import os, json, re, time, requests, difflib

    UA = {"User-Agent": "Mozilla/5.0 (compatible; TullmanBackend/1.0; +https://tullman.ai)"}
    HOWARD_URLS = [
        "https://blogspot.tullman.com/",
        "https://www.inc.com/howard-tullman",
        "https://www.howardtullman.com/",
        "https://en.wikipedia.org/wiki/Howard_Tullman",
    ]

    # ----------------- helpers -----------------
    def load_json(path, default):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def load_rules():
        return load_json(rules_path, {})

    def rules_match(patterns, prompt):
        if not patterns: return False
        for pat in patterns:
            try:
                if re.search(pat, prompt, flags=re.I):
                    return True
            except re.error:
                if pat.lower() in prompt.lower():
                    return True
        return False

    def golden_pairs():
        data = load_json(golden_path, [])
        rows = []
        if isinstance(data, list):
            for d in data:
                q = (d.get("q") or "").strip()
                a = (d.get("a") or "").strip()
                if q:
                    rows.append((q.lower(), a))
        elif isinstance(data, dict):
            for q, a in data.items():
                rows.append((str(q).strip().lower(), str(a)))
        return rows

    def golden_lookup(prompt):
        # normalize obvious name spellings
        prompt = (prompt or "").replace("Tulllman","Tullman").replace("Tulman","Tullman")
        p = prompt.strip().lower()

        pairs = golden_pairs()

        # exact
        for q, a in pairs:
            if q == p:
                return a

        # contains either way
        for q, a in pairs:
            if p in q or q in p:
                return a

        # fuzzy (typo-tolerant)
        try:
            gold_qs = [q for q, _ in pairs]
            best = difflib.get_close_matches(p, gold_qs, n=1, cutoff=0.86)
            if best:
                bq = best[0]
                for q, a in pairs:
                    if q == bq:
                        return a
        except Exception:
            pass

        return None

    def strip_html(txt):
        return re.sub(r"<[^>]+>", " ", txt or "")

    def search_corpus(prompt):
        """Return {'file': path, 'snippet': text} or None (best-effort)."""
        p = (prompt or "").strip().lower()
        try:
            for root, _, files in os.walk(corpus_dir):
                for name in files:
                    if not name.lower().endswith((
                        ".txt",".md",".html",".htm",".json",".mdx",".rst",".yaml",".yml",
                        ".ini",".cfg",".conf",".log",".sql",".csv",".tsv",".pdf"
                    )):
                        continue
                    fp = os.path.join(root, name)
                    try:
                        raw = open(fp, "r", encoding="utf-8", errors="ignore").read()
                    except Exception:
                        continue
                    text = strip_html(raw)
                    pos = text.lower().find(p)
                    if pos != -1:
                        start = max(0, pos-200); end = min(len(text), pos+200)
                        return {"file": fp, "snippet": text[start:end].strip()}
        except Exception:
            pass
        return None

    def fetch_readable(url, timeout=15):
        """Fetch via readability proxy to avoid 403 blocks (no search engine).
           Wikipedia: use REST summary API for clean text. Returns text or ''. """
        try:
            if "wikipedia.org/wiki/" in url:
                title = url.split("/wiki/", 1)[-1].replace(" ", "_")
                api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
                wr = requests.get(api, timeout=timeout, headers=UA)
                if wr.status_code == 200:
                    j = wr.json()
                    txt = (j.get("extract") or "")
                    if len(txt) >= 180:
                        return txt[:20000]
            proxy = "https://r.jina.ai/http://" + url.replace("https://","").replace("http://","")
            r = requests.get(proxy, timeout=timeout, headers=UA)
            if r.status_code == 200:
                text = re.sub(r"\s+", " ", r.text).strip()
                if len(text) >= 180:
                    return text[:20000]
        except Exception:
            pass
        return ""

    def gather_howard_context(prompt, budget_sec=40):
        """Grab text from curated Howard sources within ~40s; keep up to 4 hits."""
        t0 = time.monotonic()
        hits = []
        for u in HOWARD_URLS:
            if time.monotonic() - t0 > budget_sec:
                break
            txt = fetch_readable(u, timeout=15)
            if txt:
                hits.append({"url": u, "text": txt[:15000]})
            if len(hits) >= 4:
                break
        return hits

    def gpt_weave(prompt, hits):
        """Ask GPT to weave a quote/anecdote from the supplied sources (needs OPENAI_API_KEY)."""
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_APIKEY")
        if not key:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)

            parts = []
            for h in hits[:4]:
                excerpt = h["text"][:1500]
                parts.append(f"SOURCE: {h['url']}\nEXCERPT:\n{excerpt}\n")
            ctx = ("QUESTION: " + prompt + "\n\n" + "\n\n".join(parts)).strip()

            messages = [
                {"role":"system","content":(
                    "You are Howard Tullman. Answer crisply, no fluff. "
                    "If a source excerpt is relevant, weave a direct quote or anecdote from it. "
                    "Do NOT invent quotes. Include a single inline cite like (source: URL). "
                    "Do NOT quote Wikipedia (context-only). "
                    "If none are relevant, answer from first principles in Howard’s voice."
                )},
                {"role":"user","content": ctx},
            ]
            resp = client.chat.completions.create(
                model="gpt-4o-mini", messages=messages,
                temperature=0.35, max_tokens=900, timeout=55
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return None

    @app.route("/api/retrieve", methods=["POST"])
    def api_retrieve():
        data = request.get_json(force=True) or {}
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return jsonify({"error": "empty prompt"}), 400

        # 0) rules
        rules = load_rules()
        deny_patterns  = rules.get("deny_patterns")  or []
        force_golden   = rules.get("force_golden")   or []
        force_examples = rules.get("force_examples") or []
        deny_message   = rules.get("deny_message")   or "I don’t discuss that. Please ask me something else."

        if rules_match(deny_patterns, prompt):
            return jsonify({"answer": deny_message, "source":"policy", "session_id": None})

        if rules_match(force_examples, prompt):
            ex = Example.query.filter(Example.primary_question.ilike(f"%{prompt}%")).first()
            if ex:
                return jsonify({"answer": ex.answer, "source":"examples-forced", "session_id": None})

        if rules_match(force_golden, prompt):
            ans = golden_lookup(prompt)
            if ans:
                return jsonify({"answer": ans, "source":"golden-forced", "session_id": None})

        # 1) golden
        ans = golden_lookup(prompt)
        if ans:
            return jsonify({"answer": ans, "source":"golden", "session_id": None})

        # 2) corpus
        hit = search_corpus(prompt)
        if hit:
            return jsonify({
                "answer": f"(from corpus: {os.path.basename(hit['file'])}) {hit['snippet']}",
                "source": "corpus", "session_id": None
            })

        # 3) GPT-internet (curated Howard sources, no search engine)
        hits = gather_howard_context(prompt, budget_sec=40)
        if hits:
            woven = gpt_weave(prompt, hits)
            if woven:
                # prefer article pages over author/home if deeper links exist
                urls = [h["url"] for h in hits]
                srcs = urls[:]
                return jsonify({
                    "answer": woven, "source":"internet-howard",
                    "session_id": None, "sources": srcs
                })

        # 4) OpenAI plain fallback (if configured)
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_APIKEY")
        if key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=key)
                messages = [
                    {"role":"system","content":"You are Howard Tullman. Answer crisply in his voice."},
                    {"role":"user","content": prompt}
                ]
                resp = client.chat.completions.create(
                    model="gpt-4o-mini", messages=messages,
                    temperature=0.35, max_tokens=600, timeout=30
                )
                answer = (resp.choices[0].message.content or "").strip()
                return jsonify({"answer": answer, "source":"openai", "session_id": None})
            except Exception:
                pass

        # 5) Examples fallback
        ex2 = Example.query.filter(Example.primary_question.ilike(f"%{prompt}%")).first()
        if ex2:
            return jsonify({"answer": ex2.answer, "source":"example-fallback", "session_id": None})

        return jsonify({"answer": "(no match yet)", "source": "fallback", "session_id": None})
