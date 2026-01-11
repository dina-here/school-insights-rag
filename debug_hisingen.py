#!/usr/bin/env python3
"""
Debug: Check what Hisingen data is in PostgreSQL
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL missing in .env")
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 80)
print("Checking grundskoleforvaltning_goteborg_syntetisk_data.csv in PostgreSQL")
print("=" * 80)

# Count total rows for this file
cur.execute(
    "SELECT COUNT(*) FROM school_embeddings WHERE source_file = %s;",
    ("grundskoleforvaltning_goteborg_syntetisk_data.csv",),
)
total = cur.fetchone()[0]
print(f"\nTotal chunks: {total}")

# Show sample of chunk text
cur.execute(
    """SELECT chunk_text FROM school_embeddings 
       WHERE source_file = %s 
       LIMIT 1;""",
    ("grundskoleforvaltning_goteborg_syntetisk_data.csv",),
)
chunk = cur.fetchone()
if chunk:
    print("\nSample chunk text (first 500 chars):")
    print(chunk[0][:500])
    print("\n...")

# Check if we can find Hisingen mentions
print("\n" + "=" * 80)
print("Searching for 'Hisingen' in chunks...")
print("=" * 80)
cur.execute(
    """SELECT COUNT(*) FROM school_embeddings 
       WHERE source_file = %s 
       AND chunk_text ILIKE '%Hisingen%';""",
    ("grundskoleforvaltning_goteborg_syntetisk_data.csv",),
)
hisingen_chunks = cur.fetchone()[0]
print(f"Chunks mentioning 'Hisingen': {hisingen_chunks}")

# Check for specific school mentions
print("\nSearching for individual Hisingen schools (Skola_02, 03, 14, 15, 18, 19, 25, 26)...")
for school in ["Skola_02", "Skola_03", "Skola_14", "Skola_15", "Skola_18", "Skola_19", "Skola_25", "Skola_26"]:
    cur.execute(
        """SELECT COUNT(*) FROM school_embeddings 
           WHERE source_file = %s 
           AND chunk_text ILIKE %s;""",
        ("grundskoleforvaltning_goteborg_syntetisk_data.csv", f"%{school}%"),
    )
    count = cur.fetchone()[0]
    print(f"  {school}: {count} chunks")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("Analysis")
print("=" * 80)
print("If chunks are 0 or very low, the RAG retrieval won't find Hisingen data.")
print("Solution: Re-run ingest with smaller chunk_size to split data more finely.")
