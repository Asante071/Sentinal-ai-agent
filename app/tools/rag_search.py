from app.rag.vector_store import search_vector_store


def search_knowledge(query: str) -> str:
    results = search_vector_store(query, n_results=1)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        return "No relevant knowledge-base information was found."

    output = []

    for i, document in enumerate(documents):
        source = metadatas[i]["source"]
        distance = distances[i]

        output.append(
            f"Source: {source}\n"
            f"Chroma distance: {distance:.4f}\n\n"
            f"{document}"
        )

    return "\n\n---\n\n".join(output)
