import os

from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL is missing. "
            "Please add it to the .env file."
        )

    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)

    return conn


def create_tables():
    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # Enable pgvector
            cur.execute("""
                CREATE EXTENSION IF NOT EXISTS vector;
            """)

            # Main RAG table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    document_name TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    page_number INTEGER,
                    section TEXT,
                    source_type TEXT,
                    embedding vector(384)
                );
            """)

        conn.commit()

        print("Database tables created successfully.")

    finally:
        conn.close()


if __name__ == "__main__":
    create_tables()