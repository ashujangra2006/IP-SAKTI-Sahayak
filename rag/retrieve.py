import re

from sentence_transformers import SentenceTransformer

try:
    from .db import get_connection
except ImportError:
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

    query_lower = query.lower()

    # --------------------------------------------------
    # DOCUMENT-AWARE BOOSTING
    # --------------------------------------------------

    document_aliases = {
        "nagoya": [
            "Nagoya_Protocol.pdf"
        ],
        "nagoya protocol": [
            "Nagoya_Protocol.pdf"
        ],
        "trips": [
            "TRIPS_Agreement.pdf"
        ],
        "trips agreement": [
            "TRIPS_Agreement.pdf"
        ],
        "pct": [
            "PCT_Treaty.pdf"
        ],
        "pct treaty": [
            "PCT_Treaty.pdf"
        ],
        "budapest": [
            "Budapest_Treaty.pdf"
        ],
        "budapest treaty": [
            "Budapest_Treaty.pdf"
        ],
        "madrid": [
            "Madrid_Agreement.pdf"
        ],
        "madrid agreement": [
            "Madrid_Agreement.pdf"
        ],
        "wipo gratk": [
            "WIPO_GRATK_Treaty_2024.pdf"
        ],
        "gratk": [
            "WIPO_GRATK_Treaty_2024.pdf"
        ],
        "traditional knowledge": [
            "TK_Patent_Guidelines.pdf"
        ],
        "tkdl": [
            "TK_Patent_Guidelines.pdf"
        ],
        "patent": [
            "contentThe_Patents_Act_1970.pdf",
            "Patents_Rules_2003.pdf",
            "Patent_Office_Manual.pdf"
        ],
        "patents act": [
            "contentThe_Patents_Act_1970.pdf"
        ],
        "biodiversity": [
            "Biological_Diversity_Act_2002.pdf",
            "Biological_Diversity_Rules_2004.pdf",
            "Biological_Diversity_Rules_2024.pdf",
            "Biological_Diversity_Amendment_Rules_2025.pdf"
        ],
        "abs": [
            "NBA_ABS_Guidelines.pdf",
            "Nagoya_Protocol.pdf",
            "Biological_Diversity_Act_2002.pdf",
            "Biological_Diversity_Rules_2024.pdf"
        ],
        "geographical indication": [
            "Geographical_Indications_Act_1999.pdf"
        ],
        "gi": [
            "Geographical_Indications_Act_1999.pdf"
        ],
        "copyright": [
            "Copyright_Act_1957.pdf"
        ],
        "ayurveda aahar": [
            "FSSAI_Ayurveda_Aahar_Regulations.pdf"
        ],
        "fssai": [
            "FSSAI_Ayurveda_Aahar_Regulations.pdf"
        ],
        "drugs and cosmetics": [
            "Drugs_and_Cosmetics_Act_1940.pdf"
        ],
        "magic remedies": [
            "Drugs_and_Magic_Remedies_Act_1954.pdf"
        ],
        "ppvfr": [
            "PPVFR_Act_2001.pdf"
        ]
    }

    # Find explicitly mentioned documents
    matched_documents = set()

    for alias, documents in document_aliases.items():
        if alias in query_lower:
            matched_documents.update(documents)

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # --------------------------------------------------
            # 1. SEMANTIC VECTOR SEARCH
            # --------------------------------------------------

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
                    LIMIT 80;
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
                    LIMIT 80;
                    """,
                    (
                        query_embedding,
                        query_embedding,
                    )
                )

            vector_rows = cur.fetchall()

            # --------------------------------------------------
            # 2. EXACT DOCUMENT SEARCH
            # --------------------------------------------------

            exact_rows = []

            if matched_documents:

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
                            0.90 AS similarity
                        FROM document_chunks
                        WHERE jurisdiction = %s
                        AND document_name = ANY(%s)
                        LIMIT 40;
                        """,
                        (
                            jurisdiction,
                            list(matched_documents),
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
                            0.90 AS similarity
                        FROM document_chunks
                        WHERE document_name = ANY(%s)
                        LIMIT 40;
                        """,
                        (
                            list(matched_documents),
                        )
                    )

                exact_rows = cur.fetchall()

            # --------------------------------------------------
            # 3. MERGE VECTOR + EXACT RESULTS
            # --------------------------------------------------

            rows = vector_rows + exact_rows

    finally:
        conn.close()

    # --------------------------------------------------
    # 4. LEGAL RERANKING
    # --------------------------------------------------

    candidates = []

    seen = set()

    for row in rows:

        content = row[0] or ""
        document_name = row[1] or ""

        content_lower = content.lower()
        document_lower = document_name.lower()

        similarity = float(row[6])

        # Avoid duplicate chunks
        unique_key = (
            document_name,
            row[2],
            row[3],
            content[:100]
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)

        # --------------------------------------------------
        # KEYWORD SCORE
        # --------------------------------------------------

        keyword_matches = 0

        for keyword in keywords:

            if keyword in content_lower:
                keyword_matches += 1

        keyword_score = (
            keyword_matches / max(len(keywords), 1)
        )

        # --------------------------------------------------
        # DOCUMENT MATCH SCORE
        # --------------------------------------------------

        document_score = 0.0

        if matched_documents:

            if document_name in matched_documents:
                document_score = 1.0

        # --------------------------------------------------
        # EXACT QUERY TERM BOOST
        # --------------------------------------------------

        exact_term_boost = 0.0

        for alias in document_aliases:

            if alias in query_lower:

                if alias in document_lower:
                    exact_term_boost = 1.0

        # --------------------------------------------------
        # FINAL SCORE
        # --------------------------------------------------

        final_score = (
            similarity * 0.65
            + keyword_score * 0.15
            + document_score * 0.15
            + exact_term_boost * 0.05
        )

        candidates.append({
            "content": content,
            "document_name": document_name,
            "page_number": row[2],
            "section": row[3],
            "jurisdiction": row[4],
            "source_type": row[5],
            "similarity": similarity,
            "keyword_score": keyword_score,
            "document_score": document_score,
            "final_score": final_score,
        })

    # --------------------------------------------------
    # 5. SORT BEST RESULTS FIRST
    # --------------------------------------------------

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