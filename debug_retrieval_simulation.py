#!/usr/bin/env python3
"""Simulate what the RAG actually retrieves"""
import os
import re
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get ALL chunks (this simulates retrieving all 15 chunks)
cur.execute("""
    SELECT chunk_text 
    FROM school_embeddings 
    WHERE source_file = 'elever_students.csv'
    ORDER BY start_row;
""")

all_chunks = cur.fetchall()
print(f"Total chunks available: {len(all_chunks)}\n")

# Combine all text from all chunks
all_text = "\n".join([chunk[0] for chunk in all_chunks])

# Count 2025 entries
schools_2025 = {}
pattern = r'Year:\s*2025,\s*School:\s*(\S+),\s*Enrolled_Students:\s*(\d+)'
matches = re.findall(pattern, all_text)

print("=== ALL 2025 DATA IN DATABASE ===")
for school, students in matches:
    schools_2025[school] = int(students)
    print(f"{school}: {students}")

print(f"\n=== SUMMARY ===")
print(f"Total schools with 2025 data: {len(schools_2025)}")
print(f"Total students: {sum(schools_2025.values())}")

# Now let's see what happens if AI only gets SOME chunks (simulate top 10)
print("\n\n=== SIMULATION: AI gets only first 10 chunks (out of 15) ===")
limited_text = "\n".join([chunk[0] for chunk in all_chunks[:10]])
matches_limited = re.findall(pattern, limited_text)
schools_limited = {}
for school, students in matches_limited:
    schools_limited[school] = int(students)

print(f"Schools retrieved: {len(schools_limited)}")
print(f"Total students: {sum(schools_limited.values())}")
print(f"Missing schools: {set(schools_2025.keys()) - set(schools_limited.keys())}")

cur.close()
conn.close()
