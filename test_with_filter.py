#!/usr/bin/env python3
"""Test with NEW filtering logic"""
import os
import re
from dotenv import load_dotenv
from rag_backend_postgres import get_school_analysis, build_sources_markdown

load_dotenv()

# Simulate exact query from user
query = "Hur många elever finns det totalt?"
print(f"Query: {query}\n")

# Get data exactly as app.py does
docs = get_school_analysis(query, top_k=40)
print(f"Total docs retrieved initially: {len(docs)}\n")

# Apply the NEW filtering logic from app.py
ql = query.lower()
if (("elever" in ql or "students" in ql) and 
    ("totalt" in ql or "total" in ql or "antal" in ql or "many" in ql or "count" in ql)):
    print("Applying filter: keeping only elever_students.csv\n")
    docs = [d for d in docs if d.get("file") == "elever_students.csv"]

print(f"Docs after filtering: {len(docs)}\n")

# Combine text with NEW limit
context = "\n\n".join(f"- {d['text']}" for d in docs)[:35000]

# Count 2025 entries in the context
pattern = r'Year:\s*2025,\s*School:\s*(\S+),\s*Enrolled_Students:\s*(\d+)'
matches = re.findall(pattern, context)

schools_2025 = {}
for school, students in matches:
    schools_2025[school] = int(students)

print(f"=== DATA IN CONTEXT ===")
print(f"2025 Schools found: {len(schools_2025)}")
print(f"2025 Total students: {sum(schools_2025.values())}")
print(f"\nContext length: {len(context)} characters")
full_context = '\n\n'.join(f'- {d["text"]}' for d in docs)
print(f"Context truncated: {len(full_context) > 35000}")

# Show first few schools
print(f"\nFirst 5 schools: {list(schools_2025.items())[:5]}")

if len(schools_2025) == 25 and sum(schools_2025.values()) == 12607:
    print("\n✓ CORRECT DATA WILL BE SENT TO AI!")
else:
    print(f"\n✗ Still incorrect - missing {25-len(schools_2025)} schools")
