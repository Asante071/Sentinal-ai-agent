from pathlib import Path


KNOWLEDGE_BASE_DIR = Path("data/knowledge_base")


def load_documents():
    documents = []

    for file_path in KNOWLEDGE_BASE_DIR.glob("*.txt"):
        content = file_path.read_text(encoding="utf-8")

        documents.append({
            "filename": file_path.name,
            "content": content
        })

    return documents


def search_documents(query: str):
    documents = load_documents()

    query_words = set(query.lower().split())

    results = []

    for document in documents:

        content_lower = document["content"].lower()

        score = sum(
            1
            for word in query_words
            if word in content_lower
        )

        if score > 0:
            results.append({
                "filename": document["filename"],
                "content": document["content"],
                "score": score
            })

    results.sort(
        key=lambda result: result["score"],
        reverse=True
    )

    return results