#!/usr/bin/env python3
"""
Setup PostgreSQL database with pgvector extension
Run this once after creating your Render PostgreSQL database
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file")
    print("Add your Render PostgreSQL connection string to .env:")
    print("DATABASE_URL=postgresql://user:password@host/dbname")
    exit(1)

try:
    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Creating vector extension...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    print("Creating school_embeddings table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS school_embeddings (
            id TEXT PRIMARY KEY,
            embedding vector(768),
            chunk_text TEXT,
            source_file TEXT,
            start_row INTEGER,
            end_row INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    print("Creating index on embeddings...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS school_embeddings_idx 
        ON school_embeddings 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    
    cur.close()
    conn.close()
    
    print("✅ Database setup complete!")
    print("✅ Vector extension enabled")
    print("✅ Table created: school_embeddings")
    print("✅ Index created for fast similarity search")
    
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
