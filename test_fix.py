#!/usr/bin/env python3
"""Test the RAG retrieval after fix"""
import os
from dotenv import load_dotenv
from rag_backend_postgres import get_school_analysis
import re

load_dotenv()

# Test query about 2025 student count
print("Testing query: 'hur många elever totalt 2025?'\n")
results = get_school_analysis("hur många elever totalt 2025?", top_k=20)

print(f"Number of chunks retrieved: {len(results)}\n")

# Combine all text
all_text = "\n".join([doc['text'] for doc in results])

# Count 2025 entries
pattern = r'Year:\s*2025,\s*School:\s*(\S+),\s*Enrolled_Students:\s*(\d+)'
matches = re.findall(pattern, all_text)

schools_2025 = {}
for school, students in matches:
    schools_2025[school] = int(students)

print(f"=== RETRIEVED 2025 DATA ===")
print(f"Schools found: {len(schools_2025)}")
print(f"Total students: {sum(schools_2025.values())}")
print(f"\nSchools: {sorted(schools_2025.keys())}")

print("\n=== EXPECTED ===")
print("Schools: 25")
print("Total students: 12607")

if len(schools_2025) == 25 and sum(schools_2025.values()) == 12607:
    print("\n✓ FIX SUCCESSFUL!")
else:
    print(f"\n✗ Still missing {25 - len(schools_2025)} schools")
