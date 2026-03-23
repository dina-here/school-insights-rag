#!/usr/bin/env python3
"""
CSV Data Ingestion for PostgreSQL with pgvector
Loads school-related CSV files and uploads them to PostgreSQL for semantic search.
"""

import os
import csv
import logging
import time
import psycopg2
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from google import genai
from google.genai import errors as genai_errors
from openai import OpenAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.environ["DATABASE_URL"]
TARGET_DIM = int(os.getenv("EMBED_DIM", "768"))

client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Track OpenAI usage
OPENAI_USAGE_TRACKER = {
    "total_requests": 0,
    "max_openai_requests": 15,
}


def embed_text(text: str) -> List[float]:
    """Embed text using Gemini with optional OpenAI fallback."""
    
    # Try Gemini first
    try:
        res = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        vec = res.embeddings[0].values
        
        # Ensure dimension matches target
        n = len(vec)
        if n == TARGET_DIM:
            return vec
        if n % TARGET_DIM == 0:
            step = n // TARGET_DIM
            return [sum(vec[i*step:(i+1)*step]) / step for i in range(TARGET_DIM)]
        stride = n / TARGET_DIM
        return [vec[int(i*stride)] for i in range(TARGET_DIM)]
        
    except genai_errors.ClientError as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
            logger.warning("Gemini quota exhausted (429). Trying OpenAI fallback...")
            # Fall through to OpenAI fallback below
        else:
            logger.error(f"Gemini error: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error with Gemini: {e}")
        raise
    
    # Fallback to OpenAI if Gemini fails (limited usage for cost control)
    if openai_client:
        if OPENAI_USAGE_TRACKER["total_requests"] < OPENAI_USAGE_TRACKER["max_openai_requests"]:
            try:
                logger.info(f"Using OpenAI fallback ({OPENAI_USAGE_TRACKER['total_requests']}/{OPENAI_USAGE_TRACKER['max_openai_requests']})...")
                response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                OPENAI_USAGE_TRACKER["total_requests"] += 1
                vec = response.data[0].embedding
                
                n = len(vec)
                if n == TARGET_DIM:
                    return vec
                if n % TARGET_DIM == 0:
                    step = n // TARGET_DIM
                    return [sum(vec[i*step:(i+1)*step]) / step for i in range(TARGET_DIM)]
                stride = n / TARGET_DIM
                return [vec[int(i*stride)] for i in range(TARGET_DIM)]
                
            except Exception as e:
                logger.warning(f"OpenAI embedding failed: {e}. Retrying with Gemini after delay...")
                time.sleep(3)  # Wait before retrying Gemini
                # Retry Gemini once more
                res = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                )
                vec = res.embeddings[0].values
                n = len(vec)
                if n == TARGET_DIM:
                    return vec
                if n % TARGET_DIM == 0:
                    step = n // TARGET_DIM
                    return [sum(vec[i*step:(i+1)*step]) / step for i in range(TARGET_DIM)]
                stride = n / TARGET_DIM
                return [vec[int(i*stride)] for i in range(TARGET_DIM)]
        else:
            logger.error("OpenAI quota reached. Retrying with Gemini after delay...")
            time.sleep(3)
            # Retry Gemini
            res = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
            )
            vec = res.embeddings[0].values
            n = len(vec)
            if n == TARGET_DIM:
                return vec
            if n % TARGET_DIM == 0:
                step = n // TARGET_DIM
                return [sum(vec[i*step:(i+1)*step]) / step for i in range(TARGET_DIM)]
            stride = n / TARGET_DIM
            return [vec[int(i*stride)] for i in range(TARGET_DIM)]
    else:
        logger.warning("No OpenAI fallback configured. Retrying with Gemini after delay...")
        time.sleep(3)
        # Retry Gemini
        res = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        vec = res.embeddings[0].values
        n = len(vec)
        if n == TARGET_DIM:
            return vec
        if n % TARGET_DIM == 0:
            step = n // TARGET_DIM
            return [sum(vec[i*step:(i+1)*step]) / step for i in range(TARGET_DIM)]
        stride = n / TARGET_DIM
        return [vec[int(i*stride)] for i in range(TARGET_DIM)]


def load_csv_file(filepath: str) -> List[Dict[str, Any]]:
    """Load a CSV file with auto-detection of delimiter and encoding.
    
    Supports both ',' and ';' delimiters and multiple character encodings
    (UTF-8 with/without BOM, Latin-1, Windows-1252).
    """
    rows = []
    encodings = ['utf-8-sig', 'utf-8', 'iso-8859-1', 'cp1252', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                # Read first line to detect delimiter
                first_line = f.readline()
                if not first_line:
                    logger.warning(f"Empty file: {filepath}")
                    return []
                
                # Detect delimiter: semicolon has priority if present
                detected_delimiter = ';' if ';' in first_line else ','
                
                # Reset file pointer and parse with detected delimiter
                f.seek(0)
                reader = csv.DictReader(f, delimiter=detected_delimiter)
                for row in reader:
                    if any(row.values()):  # Skip empty rows
                        rows.append(row)
                
                logger.info(f"Loaded {len(rows)} rows from {filepath} "
                           f"(encoding={encoding}, delimiter='{detected_delimiter}')")
                return rows
                
        except UnicodeDecodeError as e:
            logger.debug(f"Encoding '{encoding}' failed for {filepath}: {e}")
            continue
        except Exception as e:
            logger.debug(f"Error with encoding '{encoding}' for {filepath}: {e}")
            continue
    
    # If all encodings failed
    logger.error(f"Could not load {filepath} with any supported encoding. Tried: {encodings}")
    raise ValueError(f"Failed to load {filepath}. File may have unsupported encoding.")
    
    return rows


def create_chunks_from_csv(filepath: str, filename: str, chunk_size: int = 5) -> List[Dict[str, Any]]:
    """Create text chunks from CSV data."""
    rows = load_csv_file(filepath)
    chunks = []
    
    for i in range(0, len(rows), chunk_size):
        chunk_rows = rows[i:i+chunk_size]
        chunk_text = f"Data from {filename}:\n"
        
        for row in chunk_rows:
            row_text = ", ".join([f"{k}: {v}" for k, v in row.items()])
            chunk_text += f"  {row_text}\n"
        
        chunks.append({
            "text": chunk_text,
            "source_file": filename,
            "start_row": i,
            "end_row": min(i + chunk_size, len(rows))
        })
    
    logger.info(f"Created {len(chunks)} chunks from {filename}")
    return chunks


def ingest_school_data(data_dir: str = "data") -> int:
    """Ingest all CSV files into PostgreSQL."""
    
    if not os.path.exists(data_dir):
        logger.error(f"Data directory {data_dir} not found")
        return 0
    
    # Find all CSV files in the directory
    csv_files = []
    if os.path.isfile(data_dir) and data_dir.endswith('.csv'):
        csv_files = [data_dir]
    else:
        for file in os.listdir(data_dir):
            if file.endswith('.csv'):
                csv_files.append(os.path.join(data_dir, file))
    
    if not csv_files:
        logger.warning(f"No CSV files found in {data_dir}")
        return 0
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    total_uploaded = 0
    
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        logger.info(f"Processing {filename}...")
        # Purge existing chunks for this source to avoid mixed chunk sizes
        try:
            cur.execute("DELETE FROM school_embeddings WHERE source_file = %s", (filename,))
            conn.commit()
            logger.info(f"Purged existing chunks for {filename}")
        except Exception as e:
            logger.warning(f"Could not purge {filename}: {e}")
        
        chunks = create_chunks_from_csv(filepath, filename)
        
        # Upload chunks to PostgreSQL
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{filename}_{idx}"
            logger.info(f"Embedding chunk {idx+1}/{len(chunks)} from {filename}...")
            vec = embed_text(chunk["text"])
            
            # Insert into PostgreSQL
            cur.execute("""
                INSERT INTO school_embeddings (id, embedding, chunk_text, source_file, start_row, end_row)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    chunk_text = EXCLUDED.chunk_text,
                    source_file = EXCLUDED.source_file,
                    start_row = EXCLUDED.start_row,
                    end_row = EXCLUDED.end_row;
            """, (
                chunk_id,
                vec,
                chunk["text"],
                chunk["source_file"],
                chunk["start_row"],
                chunk["end_row"]
            ))
            
            time.sleep(1.5)  # Longer delay to avoid rate limits
        
        conn.commit()
        logger.info(f"Uploaded {len(chunks)} chunks from {filename}")
        total_uploaded += len(chunks)
    
    cur.close()
    conn.close()
    
    logger.info(f"Total chunks uploaded: {total_uploaded}")
    logger.info(f"OpenAI usage: {OPENAI_USAGE_TRACKER['total_requests']}/{OPENAI_USAGE_TRACKER['max_openai_requests']}")
    return total_uploaded


if __name__ == "__main__":
    import sys
    
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    
    logger.info("Starting school data ingestion to PostgreSQL...")
    total = ingest_school_data(data_dir)
    logger.info(f"Completed! {total} chunks uploaded to PostgreSQL.")
