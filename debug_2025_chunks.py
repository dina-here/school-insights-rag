#!/usr/bin/env python3
"""Debug script to check 2025 data in database chunks"""
import os
import re
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get all chunks from elever_students.csv
cur.execute("""
    SELECT id, chunk_text, start_row, end_row 
    FROM school_embeddings 
    WHERE source_file = 'elever_students.csv'
    ORDER BY start_row;
""")

all_chunks = cur.fetchall()
print(f"Total chunks for elever_students.csv: {len(all_chunks)}\n")

# Count 2025 entries across all chunks
total_2025_schools = set()
for chunk_id, chunk_text, start_row, end_row in all_chunks:
    # Count 2025 entries in this chunk
    matches = re.findall(r'^2025,(\S+),(\d+)', chunk_text, re.MULTILINE)
    if matches:
        print(f"Chunk {chunk_id} (rows {start_row}-{end_row}):")
        for school, students in matches:
            print(f"  - {school}: {students} students")
            total_2025_schools.add(school)

print(f"\n=== SUMMARY ===")
print(f"Total unique schools with 2025 data in DB: {len(total_2025_schools)}")
print(f"Schools: {sorted(total_2025_schools)}")

# Now simulate what a query would retrieve (limited to 15 chunks)
print(f"\n=== SIMULATION: If only top 15 chunks retrieved ===")
limited_2025_schools = set()
limited_total = 0
for i, (chunk_id, chunk_text, start_row, end_row) in enumerate(all_chunks[:15]):
    matches = re.findall(r'^2025,(\S+),(\d+)', chunk_text, re.MULTILINE)
    for school, students in matches:
        limited_2025_schools.add(school)
        limited_total += int(students)

print(f"Schools retrieved: {len(limited_2025_schools)}")
print(f"Total students: {limited_total}")

cur.close()
conn.close()
