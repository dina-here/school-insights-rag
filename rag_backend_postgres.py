# rag_backend_postgres.py
import os
import re
import json
from typing import List, Dict, Any

from dotenv import load_dotenv
from google import genai
from openai import OpenAI
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.environ["DATABASE_URL"]
TARGET_DIM = int(os.getenv("EMBED_DIM", "768"))

client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def get_district_aggregation(query: str) -> Dict[str, Any] | None:
    """
    Detect if query asks about a specific district and return aggregated stats.
    Returns None if query is not a district-level question.
    """
    districts = ["Hisingen", "Sydväst", "Centrum", "Västra"]
    query_lower = query.lower()
    
    for district in districts:
        if district.lower() in query_lower and ("genomsnitt" in query_lower or "average" in query_lower or "andel" in query_lower or "ratio" in query_lower):
            return aggregate_district_foreign_background(district)
    
    return None


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
        
        schools = sorted(list(set(r["school"].rstrip(",") for r in district_data)))
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


def embed_query(text: str) -> List[float]:
    """Embed query text using Gemini, with OpenAI fallback if quota exceeded."""
    try:
        res = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        vec = res.embeddings[0].values
    except Exception:
        # Fallback to OpenAI if Gemini fails and OpenAI is configured
        if openai_client:
            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            vec = response.data[0].embedding
        else:
            raise
    
    # Ensure dimension matches target
    n = len(vec)
    if n == TARGET_DIM:
        return vec
    if n % TARGET_DIM == 0:
        step = n // TARGET_DIM
        return [sum(vec[i*step:(i+1)*step]) / step for i in range(TARGET_DIM)]
    stride = n / TARGET_DIM
    return [vec[int(i*stride)] for i in range(TARGET_DIM)]


def get_school_analysis(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Retrieve relevant school analysis data from PostgreSQL using pgvector."""
    
    # Special case: for queries about total student counts, fetch ALL chunks from relevant files
    ql = query.lower()
    is_total_count = (("totalt" in ql or "total" in ql or "antal" in ql or "count" in ql) and 
                      ("elever" in ql or "students" in ql or "elevantal" in ql))
    
    if is_total_count:
        # For total student count queries, return ALL elever_students.csv chunks
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT 
                    id,
                    chunk_text,
                    source_file,
                    start_row,
                    end_row,
                    1.0 as score
                FROM school_embeddings
                WHERE source_file = %s
                ORDER BY start_row;
            """, ("elever_students.csv",))
            
            results = cur.fetchall()
            docs = []
            for row in results:
                docs.append({
                    "score": row[5],
                    "text": row[1],
                    "file": row[2],
                    "url": row[2],
                })
            
            # Also include grundskoleforvaltning for district identification if area is mentioned
            districts = ["Hisingen", "Sydväst", "Centrum", "Västra", "Nordost"]
            if any(d.lower() in ql for d in districts):
                cur.execute("""
                    SELECT 
                        id,
                        chunk_text,
                        source_file,
                        start_row,
                        end_row,
                        1.0 as score
                    FROM school_embeddings
                    WHERE source_file = %s
                    ORDER BY start_row;
                """, ("grundskoleforvaltning_goteborg_syntetisk_data.csv",))
                
                grundskole_results = cur.fetchall()
                for row in grundskole_results:
                    docs.append({
                        "score": row[5],
                        "text": row[1],
                        "file": row[2],
                        "url": row[2],
                    })
            
            cur.close()
            conn.close()
            return docs
        except Exception:
            cur.close()
            conn.close()
            pass
    
    # First check if this is a district-level aggregation query
    aggregation = get_district_aggregation(query)
    if aggregation and "error" not in aggregation:
        # Convert aggregation to doc format for system prompt
        doc_text = f"District {aggregation['district']} ({len(aggregation['schools'])} schools, {len(aggregation['years'])} years): "
        doc_text += f"Overall foreign background ratio: {aggregation['overall_average']:.1%}. "
        doc_text += f"Yearly: {', '.join([f'{y}: {v:.1%}' for y, v in sorted(aggregation['year_averages'].items())])}. "
        doc_text += f"Schools: {', '.join(aggregation['schools'][:3])}..."
        
        return [{
            "score": 1.0,
            "text": doc_text,
            "file": "grundskoleforvaltning_goteborg_syntetisk_data.csv",
            "url": "grundskoleforvaltning_goteborg_syntetisk_data.csv",
        }]
    
    # Fall back to vector search
    vec = embed_query(query)
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Use pgvector cosine distance operator <=>
        # The closer to 0, the more similar
        cur.execute("""
            SELECT 
                id,
                chunk_text,
                source_file,
                start_row,
                end_row,
                1 - (embedding <=> %s::vector) as score
            FROM school_embeddings
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (vec, vec, top_k))
        
        results = cur.fetchall()
        
        docs = []
        for row in results:
            docs.append({
                "score": row[5],
                "text": row[1],
                "file": row[2],
                "url": row[2],  # Use filename as URL
            })

        # If the query references forecasts/0-5 children, ensure forecast file chunks are included
        ql = query.lower()
        if ("prognos" in ql) or ("forecast" in ql) or ("0-5" in ql) or ("0–5" in ql) or ("0 to 5" in ql) or ("entrants" in ql):
            try:
                cur.execute(
                    """
                        SELECT 
                            id,
                            chunk_text,
                            source_file,
                            start_row,
                            end_row,
                            1 - (embedding <=> %s::vector) as score
                        FROM school_embeddings
                        WHERE source_file = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s;
                    """,
                    (vec, "prognosbarn_0_5_forecast.csv", vec, max(10, min(top_k, 15))),
                )
                forecast_results = cur.fetchall()
                for row in forecast_results:
                    docs.append({
                        "score": row[5],
                        "text": row[1],
                        "file": row[2],
                        "url": row[2],
                    })
            except Exception:
                # Non-fatal; continue with existing docs
                pass

        # If the query references economy/costs/budget, include economy file chunks
        if ("ekonomi" in ql) or ("economy" in ql) or ("budget" in ql) or ("kostnad" in ql) or ("cost" in ql) or ("msek" in ql):
            try:
                cur.execute(
                    """
                        SELECT 
                            id,
                            chunk_text,
                            source_file,
                            start_row,
                            end_row,
                            1 - (embedding <=> %s::vector) as score
                        FROM school_embeddings
                        WHERE source_file = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s;
                    """,
                    (vec, "ekonomi_economy.csv", vec, max(10, min(top_k, 15))),
                )
                eco_results = cur.fetchall()
                for row in eco_results:
                    docs.append({
                        "score": row[5],
                        "text": row[1],
                        "file": row[2],
                        "url": row[2],
                    })
            except Exception:
                pass

        # If the query references students/enrollment, include students file chunks
        if ("elever" in ql) or ("students" in ql) or ("enrolled" in ql) or ("student" in ql):
            try:
                cur.execute(
                    """
                        SELECT 
                            id,
                            chunk_text,
                            source_file,
                            start_row,
                            end_row,
                            1 - (embedding <=> %s::vector) as score
                        FROM school_embeddings
                        WHERE source_file = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s;
                    """,
                    (vec, "elever_students.csv", vec, 50),  # Increased limit to ensure all chunks are retrieved
                )
                stu_results = cur.fetchall()
                for row in stu_results:
                    docs.append({
                        "score": row[5],
                        "text": row[1],
                        "file": row[2],
                        "url": row[2],
                    })
            except Exception:
                pass

        return docs
        
    finally:
        cur.close()
        conn.close()


def build_sources_markdown(docs: List[Dict[str, Any]]) -> str:
    """Format sources in Swedish with numbered references."""
    lines = ["Källor:"]
    # make each file appear only once with sequential numbering
    seen = {}
    counter = 1
    for d in docs:
        file = d["file"] or "Document"
        if file in seen:
            continue
        seen[file] = True
        url = d.get("url") or file
        lines.append(f"- ^{counter} [{file}]({url})")
        counter += 1
    return "\n".join(lines)
