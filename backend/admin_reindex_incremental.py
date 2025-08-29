# /home/kmages/backend/admin_reindex_incremental.py
import os, argparse, pickle
from typing import List
import faiss
from sentence_transformers import SentenceTransformer

# Keep consistent with your production embedding (384-dim)
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

def load_or_create_index(path: str, dim: int):
    faiss_path = os.path.join(path, "index.faiss")
    meta_path  = os.path.join(path, "index.pkl")

    if os.path.exists(faiss_path) and os.path.exists(meta_path):
        index = faiss.read_index(faiss_path)
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
        # meta is expected to be a dict with "texts" list
        if "texts" not in meta:
            meta["texts"] = []
        return index, meta
    else:
        os.makedirs(path, exist_ok=True)
        index = faiss.IndexFlatIP(dim)  # cosine via normalized vectors
        meta = {"texts": []}
        return index, meta

def save_index(index, meta, path: str):
    faiss_path = os.path.join(path, "index.faiss")
    meta_path  = os.path.join(path, "index.pkl")
    faiss.write_index(index, faiss_path)
    with open(meta_path, "wb") as f:
        pickle.dump(meta, f)

def embed_texts(model: SentenceTransformer, texts: List[str]):
    embs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return embs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True, help="Edited response to add")
    parser.add_argument("--faiss_dir", required=True)
    args = parser.parse_args()

    text = args.text.strip()
    if not text:
        return

    model = SentenceTransformer(MODEL_NAME)
    emb = embed_texts(model, [text])

    index, meta = load_or_create_index(args.faiss_dir, emb.shape[1])
    index.add(emb.astype("float32"))
    meta["texts"].append(text)
    save_index(index, meta, args.faiss_dir)

if __name__ == "__main__":
    main()
