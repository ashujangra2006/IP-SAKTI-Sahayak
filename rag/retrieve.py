import re

from sentence_transformers import SentenceTransformer

from db import get_connection


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


# --------------------------------------------------
# QUERY KEYWORDS
# --------------------------------------------------

def get_keywords(query):
    words = re.findall(r"[a-zA-Z0-9()]+", query.lower())

    stop_words = {
        "what", "does", "the", "of", "say", "about",
        "is", "are", "and", "or", "to", "in", "on",
        "for", "a", "an", "this", "that"
    }

    return {
        word
        for word in words
        if word not in stop_words and len(word) > 2
    }


# --------------------------------------------------
# RETRIEVE RELEVANT CHUNKS
# --------------------------------------------------

def retrieve_context(query, jurisdiction=None, top_k=5):

    query_embedding = model.encode(
        query,
        normalize_embeddings=True
    )

    keywords = get_keywords(query)

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # First retrieve a larger candidate pool
            if jurisdiction:

                cur.execute(
                    """
                    SELECT
                        content,
                        document_name,
                        page_number,
                        section,
                        jurisdiction,
                        source_type,
                        1 - (embedding <=> %s) AS similarity
                    FROM document_chunks
                    WHERE jurisdiction = %s
                    ORDER BY embedding <=> %s
                    LIMIT 20;
                    """,
                    (
                        query_embedding,
                        jurisdiction,
                        query_embedding,
                    )
                )

            else:

                cur.execute(
                    """
                    SELECT
                        content,
                        document_name,
                        page_number,
                        section,
                        jurisdiction,
                        source_type,
                        1 - (embedding <=> %s) AS similarity
                    FROM document_chunks
                    ORDER BY embedding <=> %s
                    LIMIT 20;
                    """,
                    (
                        query_embedding,
                        query_embedding,
                    )
                )

            rows = cur.fetchall()

    finally:
        conn.close()


    # --------------------------------------------------
    # SIMPLE LEGAL KEYWORD RERANKING
    # --------------------------------------------------

    candidates = []

    for row in rows:

        content = row[0] or ""
        content_lower = content.lower()

        similarity = float(row[6])

        keyword_matches = 0

        for keyword in keywords:
            if keyword in content_lower:
                keyword_matches += 1

        keyword_score = keyword_matches / max(len(keywords), 1)

        # Vector similarity is primary.
        # Keyword overlap gives relevant legal text a small boost.
        final_score = (
            similarity * 0.85
            + keyword_score * 0.15
        )

        candidates.append({
            "content": content,
            "document_name": row[1],
            "page_number": row[2],
            "section": row[3],
            "jurisdiction": row[4],
            "source_type": row[5],
            "similarity": similarity,
            "keyword_score": keyword_score,
            "final_score": final_score,
        })


    # Highest final score first
    candidates.sort(
        key=lambda x: x["final_score"],
        reverse=True
    )

    return candidates[:top_k]


# --------------------------------------------------
# TEST RETRIEVAL
# --------------------------------------------------

if __name__ == "__main__":

    query = (
        "What does Section 3(p) of the Patents Act "
        "say about traditional knowledge?"
    )

    print()
    print("=" * 70)
    print("IP-SAKTI SAHAYAK - RAG RETRIEVAL TEST")
    print("=" * 70)

    print()
    print(f"Query: {query}")

    results = retrieve_context(
        query=query,
        jurisdiction="India",
        top_k=5
    )

    print()
    print(f"Retrieved {len(results)} relevant chunks.")

    for i, result in enumerate(results, start=1):

        print()
        print("-" * 70)
        print(f"RESULT {i}")
        print("-" * 70)

        print(f"Document     : {result['document_name']}")
        print(f"Jurisdiction : {result['jurisdiction']}")
        print(f"Page         : {result['page_number']}")
        print(f"Section      : {result['section']}")
        print(f"Source type  : {result['source_type']}")
        print(f"Similarity   : {result['similarity']:.4f}")
        print(f"Keyword score: {result['keyword_score']:.4f}")
        print(f"Final score  : {result['final_score']:.4f}")

        print()
        print("Content:")
        print(result["content"][:1200])

    print()
    print("=" * 70)
    print("RETRIEVAL TEST COMPLETE")
    print("=" * 70)