#!/usr/bin/env python3
"""Debug script to see actual chunk contents"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get first 3 chunks to see what's in them
cur.execute("""
    SELECT id, chunk_text, start_row, end_row 
    FROM school_embeddings 
    WHERE source_file = 'elever_students.csv'
    ORDER BY start_row
    LIMIT 3;
""")

chunks = cur.fetchall()
print(f"Sample chunks from elever_students.csv:\n")

for chunk_id, chunk_text, start_row, end_row in chunks:
    print(f"=== Chunk {chunk_id} (rows {start_row}-{end_row}) ===")
    print(chunk_text)
    print("\n")

cur.close()
conn.close()
