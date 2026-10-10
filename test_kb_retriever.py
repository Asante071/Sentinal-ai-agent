"""Usage (from the project folder):  python test_kb_retriever.py
Logic test with a simple stand-in for the embedding model (no downloads, no ChromaDB).
It reads the REAL articles in ./knowledge_base. Real-model quality is checked by try_kb.py."""
import math
import os
import re
import shutil
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, ".")
from app.rag import kb_retriever as kb

results = []

def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")

class HashingEmbedder:
    """Stand-in: bag-of-words hashed into a vector. Deterministic. NOT a real language model."""
    name = "hashing-stand-in"

    def encode(self, texts):
        vectors = []
        for text in texts:
            v = [0.0] * 512
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                v[zlib.crc32(word.encode()) % 512] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vectors.append([x / norm for x in v])
        return vectors


class MemoryStore:
    """Stand-in for ChromaDB with the same four methods."""
    def __init__(self):
        self.fp, self.rows, self.rebuilds = "", [], 0

    def fingerprint(self):
        return self.fp

    def rebuild(self, fp, ids, documents, embeddings, metadatas):
        self.fp, self.rebuilds = fp, self.rebuilds + 1
        self.rows = list(zip(documents, embeddings, metadatas))

    def query(self, embedding, n):
        scored = sorted(((math.dist(embedding, e), d, m) for d, e, m in self.rows), key=lambda r: r[0])
        return [{**m, "text": d, "distance": dist} for dist, d, m in scored[:n]]


KB_FOLDER = kb.kb_dir()
if not kb.kb_available():
    print(f"No articles found in '{KB_FOLDER}'. The knowledge_base folder was not found in the project folder.")
    sys.exit(1)

# 1. articles are read generically
articles = kb.load_articles(KB_FOLDER)
check("reads every article, skips README", len(articles) >= 1 and all(a["file"].lower() != "readme.md" for a in articles),
      f"({len(articles)} articles)")
check("every article has an ID and text", all(a["id"] and a["text"] for a in articles))
print("   ", ", ".join(a["id"] for a in articles))

# 2. fingerprint is stable and changes when an article changes
fp1 = kb.fingerprint(articles, "m")
check("fingerprint is stable", fp1 == kb.fingerprint(kb.load_articles(KB_FOLDER), "m"))
changed = [dict(a) for a in articles]; changed[0]["text"] += " extra"
check("fingerprint changes when an article changes", fp1 != kb.fingerprint(changed, "m"))

# 3. search returns the 3 closest, closest first, with metadata
base = kb.KnowledgeBase(KB_FOLDER, embedder=HashingEmbedder(), store=MemoryStore())
found = base.search("VPN restart failed and the gateway did not accept the session", top_k=3)
check("returns 3 results, closest first", len(found) == 3 and found[0]["distance"] <= found[1]["distance"] <= found[2]["distance"])
check("results carry id, file, title, category, text", all(k in found[0] for k in ("id", "file", "title", "category", "text")))

# 4. ranking sanity on the real articles (stand-in embedder, so this checks the mechanism only)
def top(query):
    return base.search(query, top_k=1)[0]
check("VPN question -> a VPN article", top("my vpn will not connect")["id"].startswith("KB-VPN"), top("my vpn will not connect")["id"])
check("printer question -> a printer article", top("printer hardware fault paper jam")["id"].startswith("KB-PRN"), top("printer hardware fault paper jam")["id"])
check("disabled account -> account article", top("account disabled cannot sign in")["id"].startswith("KB-ACC"), top("account disabled cannot sign in")["id"])
check("mailbox question -> email article", top("outlook mailbox full cannot send email")["id"].startswith("KB-EML"), top("outlook mailbox full cannot send email")["id"])

# 5. index rebuilds only when the articles change
store = MemoryStore()
a = kb.KnowledgeBase(KB_FOLDER, embedder=HashingEmbedder(), store=store); a.search("vpn")
b = kb.KnowledgeBase(KB_FOLDER, embedder=HashingEmbedder(), store=store); b.search("vpn")
check("index built once, reused when nothing changed", store.rebuilds == 1 and a.rebuilt and not b.rebuilt, f"(rebuilds={store.rebuilds})")
tmp = Path(tempfile.mkdtemp())
try:
    for f in KB_FOLDER.glob("*.md"):
        shutil.copy(f, tmp / f.name)
    c = kb.KnowledgeBase(tmp, embedder=HashingEmbedder(), store=store); c.search("vpn")
    check("an identical copy of the folder does not trigger a rebuild", not c.rebuilt and store.rebuilds == 1, f"(rebuilds={store.rebuilds})")
    first = sorted(tmp.glob("KB-*.md"))[0]
    first.write_text(first.read_text(encoding="utf-8") + "\nNew line added by a test.", encoding="utf-8")
    d = kb.KnowledgeBase(tmp, embedder=HashingEmbedder(), store=store); d.search("vpn")
    check("index rebuilds automatically when an article changes", d.rebuilt and store.rebuilds == 2, f"(rebuilds={store.rebuilds})")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# 6. empty or missing folder
empty = Path(tempfile.mkdtemp())
check("empty folder gives no results", kb.KnowledgeBase(empty, embedder=HashingEmbedder(), store=MemoryStore()).search("vpn") == [])
check("missing folder gives no articles", kb.load_articles(empty / "nope") == [])
shutil.rmtree(empty, ignore_errors=True)

# 7. the gateway's knowledge_search uses it and returns a citation
from app.agent.tool_gateway import ToolGateway
kb._kb = kb.KnowledgeBase(KB_FOLDER, embedder=HashingEmbedder(), store=MemoryStore())
result = ToolGateway()._knowledge_search({"query": "vpn restart failed gateway did not accept session"})
data = result["data"]
check("gateway knowledge_search: FOUND with citation", result["status"] == "FOUND" and re.match(r"KB-[A-Z]+-\d+ \(.+\)", data.get("citation", "")), data.get("citation", ""))
check("gateway knowledge_search: shows 3 results", result["message"].count("Result ") == 3 and len(data["sources"]) == 3)
check("gateway knowledge_search: empty query rejected", ToolGateway()._knowledge_search({"query": " "})["status"] == "BAD_ARGUMENTS")

# 8. summary embedding mode
sample = articles[0]
summary = kb.embedding_text(sample, "summary")
check("full mode embeds the whole article", kb.embedding_text(sample, "full") == sample["text"])
check("summary mode: title + keywords + symptoms, no resolution steps",
      sample["title"] in summary and "Resolution steps" not in summary and len(summary) < len(sample["text"]))
check("mode changes the index fingerprint", kb.fingerprint(articles, "m|full") != kb.fingerprint(articles, "m|summary"))
check("article without sections falls back to full text",
      kb.embedding_text({"title": "T", "text": "plain text only"}, "summary") == "plain text only")

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
