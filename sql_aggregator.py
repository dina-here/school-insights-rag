#!/usr/bin/env python3
"""
Direct SQL aggregator for district-level statistics.
Bypasses vector search for queries about specific districts.
Extracts from CSV text chunks and aggregates.
"""

import os
import psycopg2
import re
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

def aggregate_district_foreign_background(district: str) -> Dict[str, Any]:
    """
    Query PostgreSQL for all rows mentioning a district,
    extract foreign_background_ratio values, and compute average.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Get all chunks mentioning this district
        cur.execute(
            """SELECT chunk_text FROM school_embeddings 
               WHERE source_file = %s 
               AND chunk_text ILIKE %s;""",
            ("grundskoleforvaltning_goteborg_syntetisk_data.csv", f"%{district}%"),
        )
        
        chunks = [row[0] for row in cur.fetchall()]
        
        if not chunks:
            return {"error": f"No data found for district: {district}"}
        
        # Parse Foreign_Background_Ratio values from all chunks
        all_text = "\n".join(chunks)
        
        # Extract Year, School, District, Foreign_Background_Ratio
        # Format: "Year: 2022, School: Skola_02, District: Hisingen, ..., Foreign_Background_Ratio: 0.528, ..."
        pattern = r"Year:\s*(\d+).*?School:\s*(\S+).*?District:\s*(\S+?),.*?Foreign_Background_Ratio:\s*([\d.]+)"
        matches = re.findall(pattern, all_text, re.DOTALL)
        
        # Filter for the target district (case-insensitive)
        district_data = [
            {"year": int(m[0]), "school": m[1], "ratio": float(m[3])}
            for m in matches
            if m[2].strip().lower() == district.lower()
        ]
        
        if not district_data:
            return {"error": f"No ratio data found for district: {district}"}
        
        # Group by year and compute averages
        year_avgs = {}
        for row in district_data:
            year = row["year"]
            if year not in year_avgs:
                year_avgs[year] = []
            year_avgs[year].append(row["ratio"])
        
        year_avgs = {y: sum(v) / len(v) for y, v in year_avgs.items()}
        overall_avg = sum(r["ratio"] for r in district_data) / len(district_data)
        
        schools = list(set(r["school"] for r in district_data))
        years = sorted(year_avgs.keys())
        
        return {
            "district": district,
            "schools": schools,
            "num_schools": len(schools),
            "years": years,
            "year_averages": year_avgs,
            "overall_average": overall_avg,
            "data_points": len(district_data),
        }
    
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys
    
    district = sys.argv[1] if len(sys.argv) > 1 else "Hisingen"
    
    result = aggregate_district_foreign_background(district)
    
    import json
    print(json.dumps(result, indent=2))
