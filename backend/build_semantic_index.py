# /home/kmages/backend/build_semantic_index.py
import os, json, pickle
from sklearn.feature_extraction.text import TfidfVectorizer

BASE    = "/home/kmages/backend"
SEED    = os.path.join(BASE, "voiceprint_seed.jsonl")
GOLDEN  = "/home/kmages/golden.jsonl"
OUT_STG = os.path.join(BASE, "semantic_staging.pkl")

def load_pairs(path):
    out=[]
    if os.path.exists(path):
        with open(path,"r",encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if not line: continue
                try:
                    obj=json.loads(line)
                    q=(obj.get("prompt") or "").strip()
                    a=(obj.get("response") or "").strip()
                    if q and a: out.append((q,a))
                except: pass
    return out

def main():
    qa   = load_pairs(SEED)
    gold = load_pairs(GOLDEN)
    pairs = qa + gold
    if not pairs:
        print("[warn] no data; staging index not written")
        return
    questions = [q for q,_ in pairs]
    vec = TfidfVectorizer(lowercase=True, ngram_range=(1,2),
                          max_features=50000, strip_accents="unicode")
    X = vec.fit_transform(questions)
    with open(OUT_STG,"wb") as f:
        pickle.dump({"vectorizer": vec, "matrix": X, "pairs": pairs}, f)
    print(f"[ok] wrote {OUT_STG} | questions={len(questions)}")

if __name__ == "__main__":
    main()
