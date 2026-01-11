#!/usr/bin/env python3
"""
Check if a specific dataset/file was ingested into PostgreSQL with pgvector.
Usage:
  python check_db_file_presence.py grundskoleforvaltning_goteborg_syntetisk_data.csv
If no argument is provided, the default filename is used.
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
DEFAULT_FILENAME = "grundskoleforvaltning_goteborg_syntetisk_data.csv"

if not DATABASE_URL:
    print("ERROR: DATABASE_URL missing in .env")
    print("Add your Render connection string: DATABASE_URL=postgresql://user:pass@host/db")
    raise SystemExit(1)

filename = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILENAME

print(f"Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    # Count rows and show a couple of examples
    cur.execute(
        "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM school_embeddings WHERE source_file = %s;",
        (filename,),
    )
    count, min_ts, max_ts = cur.fetchone()
    print(f"File: {filename}")
    print(f"Rows found: {count}")
    print(f"First inserted: {min_ts}")
    print(f"Last inserted:  {max_ts}")

    if count:
        print("\nSample rows (id, start_row, end_row, text_len):")
        cur.execute(
            """
            SELECT id, start_row, end_row, LENGTH(chunk_text)
            FROM school_embeddings
            WHERE source_file = %s
            ORDER BY start_row
            LIMIT 5;
            """,
            (filename,),
        )
        for r in cur.fetchall():
            print(f"  - {r[0]} | {r[1]}-{r[2]} | len={r[3]}")

    print("\nTip: To see one full chunk text, run with SQL:\n  SELECT chunk_text FROM school_embeddings WHERE source_file = '<file>' LIMIT 1;")
finally:
    cur.close()
    conn.close()

print("Done.")
