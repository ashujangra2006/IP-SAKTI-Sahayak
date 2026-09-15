import os
import re
import sys

from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from db import get_connection


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = PROJECT_ROOT / "documents"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# --------------------------------------------------
# LOAD EMBEDDING MODEL
# --------------------------------------------------

print("Loading embedding model...")

model = SentenceTransformer(MODEL_NAME)

print("Embedding model loaded.")


# --------------------------------------------------
# TEXT CHUNKING
# --------------------------------------------------

def chunk_text(text):
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return []

    chunks = []

    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - CHUNK_OVERLAP

    return chunks


# --------------------------------------------------
# METADATA
# --------------------------------------------------

def get_jurisdiction(pdf_path):
    if "India_Law" in pdf_path.parts:
        return "India"

    if "International_Law" in pdf_path.parts:
        return "International"

    return "General"


def get_source_type(document_name):
    name = document_name.lower()

    if "act" in name:
        return "statute"

    if "rules" in name or "regulation" in name:
        return "rules"

    if "treaty" in name or "agreement" in name or "protocol" in name:
        return "treaty"

    if "manual" in name or "guideline" in name:
        return "guideline"

    return "document"


def extract_section(text):
    patterns = [
        r"\bSection\s+[\w()./-]+",
        r"\bSec\.\s*[\w()./-]+",
        r"\bRule\s+[\w()./-]+",
        r"\bArticle\s+[\w()./-]+",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(0)

    return None


# --------------------------------------------------
# INGEST ONE PDF
# --------------------------------------------------

def ingest_pdf(pdf_path):

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Please provide a PDF file.")

    document_name = pdf_path.name
    jurisdiction = get_jurisdiction(pdf_path)
    source_type = get_source_type(document_name)

    print()
    print("=" * 60)
    print(f"Document: {document_name}")
    print(f"Jurisdiction: {jurisdiction}")
    print(f"Source type: {source_type}")
    print("=" * 60)

    reader = PdfReader(str(pdf_path))

    print(f"Pages: {len(reader.pages)}")

    records = []

    for page_number, page in enumerate(reader.pages, start=1):

        try:
            text = page.extract_text() or ""
        except Exception as e:
            print(f"Could not extract page {page_number}: {e}")
            continue

        chunks = chunk_text(text)

        for chunk in chunks:

            section = extract_section(chunk)

            records.append({
                "content": chunk,
                "document_name": document_name,
                "jurisdiction": jurisdiction,
                "page_number": page_number,
                "section": section,
                "source_type": source_type,
            })

    if not records:
        print("No text found in this PDF.")
        return

    print(f"Created {len(records)} chunks.")

    # --------------------------------------------------
    # CREATE EMBEDDINGS
    # --------------------------------------------------

    texts = [record["content"] for record in records]

    print("Creating embeddings...")

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    print("Embeddings created.")

    # --------------------------------------------------
    # SAVE TO NEON
    # --------------------------------------------------

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # Remove previous copy of the same document
            cur.execute(
                """
                DELETE FROM document_chunks
                WHERE document_name = %s;
                """,
                (document_name,)
            )

            for record, embedding in zip(records, embeddings):

                cur.execute(
                    """
                    INSERT INTO document_chunks
                    (
                        content,
                        document_name,
                        jurisdiction,
                        page_number,
                        section,
                        source_type,
                        embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        record["content"],
                        record["document_name"],
                        record["jurisdiction"],
                        record["page_number"],
                        record["section"],
                        record["source_type"],
                        embedding,
                    )
                )

        conn.commit()

    finally:
        conn.close()

    print()
    print("✅ PDF successfully stored in Neon!")
    print(f"✅ Chunks inserted: {len(records)}")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("IP-SAKTI Sahayak - Batch PDF Ingestion")
    print("=" * 60)

    pdf_files = list(DOCUMENTS_DIR.rglob("*.pdf"))

    if not pdf_files:
        print("No PDF files found in documents folder.")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files.")

    successful = 0
    failed = 0

    for index, pdf_file in enumerate(pdf_files, start=1):

        print()
        print("#" * 60)
        print(f"Processing PDF {index}/{len(pdf_files)}")
        print(f"File: {pdf_file.name}")
        print("#" * 60)

        try:
            ingest_pdf(pdf_file)
            successful += 1

        except Exception as e:
            failed += 1

            print()
            print(f"❌ FAILED: {pdf_file.name}")
            print(f"Error: {e}")
            print("Continuing with next PDF...")

    print()
    print("=" * 60)
    print("BATCH INGESTION COMPLETE")
    print("=" * 60)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total PDFs: {len(pdf_files)}")
    print("=" * 60)