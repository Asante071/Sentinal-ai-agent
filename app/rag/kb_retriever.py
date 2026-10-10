"""Generic knowledge-base retriever for SentinelAI (RAG).

* Reads EVERY .md / .txt article in the knowledge-base folder (default: <project>/knowledge_base,
  change it with the environment variable KB_DIR). Nothing about the articles is hard-coded.
* One chunk per article (the articles are short). Article ID, category, title and file name are
  kept as metadata so answers can cite their source.
* The vector index rebuilds itself automatically whenever the articles change (a fingerprint of the
  files is compared), so there is no manual "build the index" step.
* Search returns the top 3 articles (not just 1) with their distance (lower = closer).

Settings (optional environment variables): KB_DIR, KB_DB_DIR, KB_EMBEDDING_MODEL, KB_MAX_DISTANCE,
KB_EMBED_MODE ("full" = embed the whole article, default; "summary" = embed title + keywords + symptoms only;
the full article is always what gets returned).
"""
import hashlib
import os
import re
from pathlib import Path

MODEL_NAME = os.getenv("KB_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
SKIP_FILES = {"readme.md", "readme.txt"}


def kb_dir():
    return Path(os.getenv("KB_DIR", "knowledge_base"))


def db_dir():
    return os.getenv("KB_DB_DIR", "data/vector_db_kb")


# ---------------------------------------------------------------- articles
def load_articles(directory):
    """Read every article in the folder. Returns a list of dicts (id, file, title, category, text)."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    articles = []
    for path in sorted(list(directory.glob("*.md")) + list(directory.glob("*.txt"))):
        if path.name.lower() in SKIP_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue
        title = re.search(r"^#\s+(.+)$", text, re.M)
        article_id = re.search(r"\*\*Article ID:\*\*\s*(\S+)", text)
        category = re.search(r"\*\*Category:\*\*\s*(.+)", text)
        articles.append({
            "id": article_id.group(1) if article_id else path.stem,
            "file": path.name,
            "title": title.group(1).strip() if title else path.stem,
            "category": category.group(1).strip() if category else "",
            "text": text,
        })
    return articles


def embedding_text(article, mode="full"):
    """The text that is turned into a vector for one article."""
    if mode != "summary":
        return article["text"]
    text = article["text"]
    keywords = re.search(r"\*\*Keywords:\*\*\s*(.+)", text)
    symptoms = re.search(r"##\s*Symptoms\s*\n(.+?)(?=\n##\s|\Z)", text, re.S)
    parts = [article["title"]]
    if keywords:
        parts.append(keywords.group(1).strip())
    if symptoms:
        parts.append(symptoms.group(1).strip())
    return "\n".join(parts) if len(parts) > 1 else text


def fingerprint(articles, model_name):
    digest = hashlib.sha256(str(model_name).encode("utf-8"))
    for article in articles:
        digest.update(article["file"].encode("utf-8"))
        digest.update(article["text"].encode("utf-8"))
    return digest.hexdigest()


# ---------------------------------------------------------------- embeddings and storage
class SentenceTransformerEmbedder:
    """Turns text into vectors (same model Asante's index uses)."""

    def __init__(self, name=MODEL_NAME):
        self.name = name
        self._model = None

    def encode(self, texts):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.name)
        return self._model.encode(list(texts)).tolist()


class ChromaStore:
    """ChromaDB on disk. Uses the same calls as Asante's working vector_store.py."""
    COLLECTION = "sentinelai_kb"

    def __init__(self, path):
        import chromadb
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.path))
        self._fingerprint_file = self.path / "fingerprint.txt"

    def fingerprint(self):
        return self._fingerprint_file.read_text().strip() if self._fingerprint_file.exists() else ""

    def rebuild(self, fp, ids, documents, embeddings, metadatas):
        try:
            self.client.delete_collection(self.COLLECTION)
        except Exception:
            pass  # nothing to delete the first time
        collection = self.client.get_or_create_collection(name=self.COLLECTION)
        collection.upsert(documents=documents, embeddings=embeddings, ids=ids, metadatas=metadatas)
        self._fingerprint_file.write_text(fp)

    def query(self, embedding, n):
        collection = self.client.get_or_create_collection(name=self.COLLECTION)
        n = min(n, collection.count())
        if n < 1:
            return []
        found = collection.query(query_embeddings=[embedding], n_results=n)
        return [{**meta, "text": doc, "distance": float(dist)}
                for doc, meta, dist in zip(found["documents"][0], found["metadatas"][0], found["distances"][0])]


# ---------------------------------------------------------------- the retriever
class KnowledgeBase:
    def __init__(self, directory=None, embedder=None, store=None):
        self.directory = Path(directory) if directory else kb_dir()
        self.embedder = embedder or SentenceTransformerEmbedder()
        self._store = store
        self.mode = os.getenv("KB_EMBED_MODE", "full")
        self._ready = False
        self.articles = []
        self.rebuilt = False  # True if this run (re)built the index

    def _prepare(self):
        if self._ready:
            return
        self.articles = load_articles(self.directory)
        if self.articles:
            self._store = self._store or ChromaStore(db_dir())
            fp = fingerprint(self.articles, f"{getattr(self.embedder, 'name', 'embedder')}|{self.mode}")
            if self._store.fingerprint() != fp:
                self._store.rebuild(
                    fp,
                    ids=[a["file"] for a in self.articles],
                    documents=[a["text"] for a in self.articles],
                    embeddings=self.embedder.encode([embedding_text(a, self.mode) for a in self.articles]),
                    metadatas=[{"id": a["id"], "file": a["file"], "title": a["title"], "category": a["category"]}
                               for a in self.articles],
                )
                self.rebuilt = True
        self._ready = True

    def search(self, query, top_k=3):
        self._prepare()
        if not self.articles:
            return []
        results = self._store.query(self.embedder.encode([query])[0], top_k)
        limit = os.getenv("KB_MAX_DISTANCE")
        if limit:
            results = [r for r in results if r["distance"] <= float(limit)]
        return results


# ---------------------------------------------------------------- module-level helpers
_kb = None


def _get():
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def kb_available():
    """True if the knowledge-base folder exists and holds at least one article."""
    return bool(load_articles(kb_dir()))


def search_kb(query, top_k=3):
    return _get().search(query, top_k)


def warm_up():
    """Load the embedding model and (re)build the index now, so the first search is fast."""
    kb = _get()
    kb._prepare()
    if kb.articles:
        kb.embedder.encode(["warm up"])


def format_results(results):
    blocks = [f"Result {i}: {r['id']} ({r['file']}), distance {r['distance']:.4f}\n\n{r['text']}"
              for i, r in enumerate(results, 1)]
    return "\n\n---\n\n".join(blocks)
