"""Usage (from the project folder):  python try_kb.py
REAL check: real embedding model + ChromaDB on Mmabotse's articles. No Gemini needed.
Shows the top 3 articles for several questions, and how long the first and second search take."""
import sys
import time

sys.path.insert(0, ".")
from app.rag import kb_retriever as kb

print("Knowledge-base folder:", kb.kb_dir().resolve())
print("Articles found:", len(kb.load_articles(kb.kb_dir())))

start = time.time()
kb.warm_up()
print(f"Model loaded and index ready in {time.time() - start:.1f} s "
      f"({'index was (re)built' if kb._get().rebuilt else 'existing index reused'})\n")

QUESTIONS = [
    "my vpn will not connect",
    "VPN restart failed, the gateway did not accept the session",
    "I forgot my password",
    "my account is disabled and I cannot sign in",
    "outlook says the mailbox is full",
    "the finance printer shows an error and will not print",
    "the print queue is stuck",
    "I need a new laptop and a second monitor",
]
for question in QUESTIONS:
    start = time.time()
    found = kb.search_kb(question, top_k=3)
    print(f"Q: {question}   ({(time.time() - start) * 1000:.0f} ms)")
    for i, r in enumerate(found, 1):
        print(f"   {i}. {r['id']:<11} {r['title']:<34} distance {r['distance']:.3f}")
    print()
