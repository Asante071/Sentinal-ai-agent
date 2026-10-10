"""Usage (from the project folder):  python eval_retrieval.py
REAL measurement (real embedding model, no Gemini): does the search find the right article?
Compares two ways of indexing the articles: "full" (whole article) and "summary" (title + keywords + symptoms).

Caution: the questions below are a SMALL hand-written set (one or two per article), so treat the result as
indicative. Mmabotse should add her own questions for the report."""
import sys

import numpy as np

sys.path.insert(0, ".")
from app.rag import kb_retriever as kb

LABELLED = [  # (what a user might write, the article that should be found first)
    ("my vpn won't connect", "KB-VPN-001"),
    ("the VPN is down and I can't reach the file server", "KB-VPN-001"),
    ("VPN restart failed and the gateway did not accept the session", "KB-VPN-001"),
    ("the VPN drops every few minutes", "KB-VPN-002"),
    ("VPN is really slow and internal apps are slow", "KB-VPN-002"),
    ("VPN says my username or password is wrong", "KB-VPN-003"),
    ("I am locked out of my account", "KB-ACC-001"),
    ("I forgot my password", "KB-ACC-002"),
    ("my account has been disabled", "KB-ACC-003"),
    ("outlook won't send my mail, the mailbox is full", "KB-EML-001"),
    ("outlook is very slow and keeps freezing", "KB-EML-002"),
    ("nobody in the office can get email, the mail service is down", "KB-EML-003"),
    ("the printer shows offline", "KB-PRN-001"),
    ("print jobs are stuck in the queue", "KB-PRN-002"),
    ("paper jam and the toner is empty", "KB-PRN-003"),
]


def evaluate(encode, articles, mode):
    vectors = np.array(encode([kb.embedding_text(a, mode) for a in articles]))
    questions = np.array(encode([q for q, _ in LABELLED]))
    top1 = top3 = 0
    misses = []
    for (question, expected), qv in zip(LABELLED, questions):
        order = sorted(range(len(articles)), key=lambda i: float(((qv - vectors[i]) ** 2).sum()))
        ids = [articles[i]["id"] for i in order]
        top1 += ids[0] == expected
        top3 += expected in ids[:3]
        if ids[0] != expected:
            misses.append((question, expected, ids[:3]))
    return top1, top3, misses


if __name__ == "__main__":
    from sentence_transformers import SentenceTransformer

    articles = kb.load_articles(kb.kb_dir())
    print(f"{len(articles)} articles, {len(LABELLED)} questions, model {kb.MODEL_NAME}\n")
    model = SentenceTransformer(kb.MODEL_NAME)
    encode = lambda texts: model.encode(list(texts))
    for mode in ("full", "summary"):
        top1, top3, misses = evaluate(encode, articles, mode)
        print(f"mode = {mode:<8} right article first: {top1}/{len(LABELLED)}   right article in top 3: {top3}/{len(LABELLED)}")
        for question, expected, got in misses:
            print(f"     missed: '{question}'  expected {expected}, got {got}")
        print()
