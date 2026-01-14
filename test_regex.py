#!/usr/bin/env python3
import re

# Simulate chunk format from ingest_school_data_postgres.py
# CSV format: "Year: 2025, School: Skola_19, Enrolled_Students: 841, Grade_F1_3: 237, ..."

sample_chunks = [
    "Data from elever_students.csv:\n  Year: 2025, School: Skola_02, Enrolled_Students: 349, Grade_F1_3: 104, Grade_4_6: 106, Grade_7_9: 119, Special_Needs_Ratio: 0.115, Foreign_Background_Ratio: 0.306, Avg_Distance_To_School_km: 4.44, Avg_Merit_Score_Grade9: 261.7\n  Year: 2025, School: Skola_03, Enrolled_Students: 491, Grade_F1_3: 175, Grade_4_6: 176, Grade_7_9: 145, Special_Needs_Ratio: 0.128, Foreign_Background_Ratio: 0.487, Avg_Distance_To_School_km: 1.22, Avg_Merit_Score_Grade9: 259.6",
    "Data from elever_students.csv:\n  Year: 2025, School: Skola_19, Enrolled_Students: 841, Grade_F1_3: 237, Grade_4_6: 274, Grade_7_9: 269, Special_Needs_Ratio: 0.105, Foreign_Background_Ratio: 0.364, Avg_Distance_To_School_km: 1.12, Avg_Merit_Score_Grade9: 249.5\n  Year: 2025, School: Skola_20, Enrolled_Students: 404, Grade_F1_3: 139, Grade_4_6: 129, Grade_7_9: 136, Special_Needs_Ratio: 0.163, Foreign_Background_Ratio: 0.525, Avg_Distance_To_School_km: 1.89, Avg_Merit_Score_Grade9: 258.7",
]

elever_text = "\n".join(sample_chunks)

print("=" * 80)
print("SAMPLE TEXT TO PARSE:")
print("=" * 80)
print(elever_text[:500])
print("\n...")

print("\n" + "=" * 80)
print("REGEX PATTERN TEST:")
print("=" * 80)

pattern = r'Year:\s*(\d+)[^,]*School:\s*([Ss]kola_\d+)[^,]*Enrolled_Students:\s*(\d+)'
matches = list(re.finditer(pattern, elever_text))

print(f"Pattern (old): {pattern}")
print(f"Found {len(matches)} matches (OLD PATTERN)\n")

# NEW PATTERN WITH DOTALL
pattern_new = r'Year:\s*(\d+).*?School:\s*([Ss]kola_\d+).*?Enrolled_Students:\s*(\d+)'
matches_new = list(re.finditer(pattern_new, elever_text, re.DOTALL))

print(f"Pattern (new): {pattern_new}")
print(f"Found {len(matches_new)} matches (NEW PATTERN)\n")

for i, match in enumerate(matches_new):
    year = int(match.group(1))
    school = match.group(2).rstrip(',').strip()
    enrolled = int(match.group(3))
    print(f"Match {i+1}: Year={year}, School={school}, Enrolled={enrolled}")

print("\n" + "=" * 80)
print("CHECKING FOR SKOLA_19:")
print("=" * 80)

skola_19_matches = [m for m in matches_new if m.group(2) == 'Skola_19']
if skola_19_matches:
    print(f"✓ Found {len(skola_19_matches)} match(es) for Skola_19")
    for m in skola_19_matches:
        print(f"  - Year: {m.group(1)}, Enrolled: {m.group(3)}")
else:
    print("✗ NO MATCHES FOR SKOLA_19!")
