#!/usr/bin/env python3
"""Test actual AI response with retrieved data"""
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
print(f"Total docs retrieved: {len(docs)}\n")

# Check how many are from elever_students.csv
elever_docs = [d for d in docs if d.get('file') == 'elever_students.csv']
print(f"Docs from elever_students.csv: {len(elever_docs)}\n")

# Combine text
context = "\n\n".join(f"- {d['text']}" for d in docs)

# Count 2025 entries in the context
pattern = r'Year:\s*2025,\s*School:\s*(\S+),\s*Enrolled_Students:\s*(\d+)'
matches = re.findall(pattern, context)

schools_2025 = {}
for school, students in matches:
    schools_2025[school] = int(students)

print(f"=== DATA IN CONTEXT ===")
print(f"2025 Schools found: {len(schools_2025)}")
print(f"2025 Total students: {sum(schools_2025.values())}")

# Also check if context is truncated
print(f"\nContext length: {len(context)} characters")
print(f"Context truncated in app.py: {len(context) > 12000}")

# Show what sources would be cited
sources = build_sources_markdown(docs)
print(f"\n{sources}")
