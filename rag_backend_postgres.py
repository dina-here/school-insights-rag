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
    
    # Special case: for queries about student counts by area, compute aggregation directly
    ql = query.lower()
    is_student_count_by_area = (("elevantal" in ql or "elever" in ql) and 
                                 any(d.lower() in ql for d in ["Hisingen", "Sydväst", "Centrum", "Västra", "Nordost"]))
    
    if is_student_count_by_area:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        try:
            # Extract which area and year are asked about
            districts = ["Hisingen", "Sydväst", "Centrum", "Västra", "Nordost"]
            target_district = None
            for d in districts:
                if d.lower() in ql:
                    target_district = d
                    break
            
            # Extract year (look for 2023, 2024, 2025)
            target_year = None
            for year in [2025, 2024, 2023]:
                if str(year) in ql:
                    target_year = year
                    break
            
            if target_district and target_year:
                # Query: sum all students for target district and year
                cur.execute("""
                    SELECT 
                        gsd.District,
                        es.Year,
                        COUNT(DISTINCT gsd.School) as school_count,
                        SUM(es.Enrolled_Students) as total_students,
                        AVG(es.Enrolled_Students) as avg_per_school
                    FROM school_embeddings se_gsd
                    JOIN school_embeddings se_es ON 1=1
                    CROSS JOIN (
                        SELECT 
                            substring(chunk_text from 'School: (\w+)') as school,
                            CAST(substring(chunk_text from 'Year: (\d+)') AS INT) as year,
                            CAST(substring(chunk_text from 'Enrolled_Students: (\d+)') AS INT) as enrolled
                        FROM school_embeddings
                        WHERE source_file = 'elever_students.csv'
                    ) es
                    CROSS JOIN (
                        SELECT 
                            substring(chunk_text from 'School: (\w+)') as school,
                            substring(chunk_text from 'District: (\w+)') as district
                        FROM school_embeddings
                        WHERE source_file = 'grundskoleforvaltning_goteborg_syntetisk_data.csv'
                    ) gsd
                    WHERE es.school = gsd.school
                        AND gsd.district = %s
                        AND es.year = %s
                    GROUP BY gsd.District, es.Year;
                """, (target_district, target_year))
                
                result = cur.fetchone()
                if result:
                    district, year, school_count, total_students, avg_per_school = result
                    doc_text = (
                        f"**Elevantal i {district} år {year}**\n"
                        f"- Antal skolor: {school_count}\n"
                        f"- Totalt elevantal: {total_students}\n"
                        f"- Genomsnitt per skola: {avg_per_school:.0f}"
                    )
                    cur.close()
                    conn.close()
                    return [{
                        "score": 1.0,
                        "text": doc_text,
                        "file": "elever_students.csv",
                        "url": "elever_students.csv",
                    }]
            
            cur.close()
            conn.close()
        except Exception as e:
            logger.warning(f"Aggregation query failed: {e}")
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


def save_chat_log(user_question: str, assistant_reply: str, source_files: str) -> None:
    """Save chat interaction to PostgreSQL for analytics."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Create table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_question TEXT NOT NULL,
                assistant_reply TEXT NOT NULL,
                source_files TEXT,
                reply_length INT
            );
        """)
        
        # Insert log entry
        cur.execute("""
            INSERT INTO chat_logs (user_question, assistant_reply, source_files, reply_length)
            VALUES (%s, %s, %s, %s);
        """, (user_question, assistant_reply, source_files, len(assistant_reply)))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving chat log: {e}")
