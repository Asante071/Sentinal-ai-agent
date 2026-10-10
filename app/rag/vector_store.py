from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


KNOWLEDGE_BASE_DIR = Path("data/knowledge_base")
VECTOR_DB_DIR = "data/vector_db"

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(
    path=VECTOR_DB_DIR
)

collection = client.get_or_create_collection(
    name="sentinelai_knowledge"
)


def build_index():

    documents = []
    ids = []
    metadatas = []

    for file_path in KNOWLEDGE_BASE_DIR.glob("*.txt"):

        content = file_path.read_text(
            encoding="utf-8"
        )

        documents.append(content)
        ids.append(file_path.stem)
        metadatas.append({
            "source": file_path.name
        })

    if not documents:
        print("No knowledge-base documents found.")
        return

    embeddings = model.encode(
        documents
    ).tolist()

    collection.upsert(
        documents=documents,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas
    )

    print(
        f"Indexed {len(documents)} knowledge-base documents."
    )


def search_vector_store(
    query: str,
    n_results: int = 2
):

    query_embedding = model.encode(
        [query]
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )

    return results