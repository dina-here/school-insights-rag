#!/usr/bin/env python3
"""
CSV Data Ingestion for School Analysis
Loads school-related CSV files and uploads them to Pinecone for semantic search.
Uses Gemini for embeddings with OpenAI fallback (limited to student projects).
"""

import os
import csv
import logging
import time
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from google import genai
from google.genai import errors as genai_errors
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX_HOST = os.environ["PINECONE_INDEX_HOST"]
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "skolanalys")

client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_INDEX_HOST)
TARGET_DIM = int(os.getenv("EMBED_DIM", "768"))

# Track OpenAI usage for student projects
OPENAI_USAGE_TRACKER = {
    "total_requests": 0,
    "max_openai_requests": 15,  # Limit to 15 OpenAI requests for student project
}


def embed_text(text: str) -> List[float]:
    """
    Embed text using Gemini embedding model with OpenAI fallback.
    Falls back to OpenAI immediately on 429 quota exhaustion.
    """
    
    # Try Gemini once
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
            logger.warning("Gemini quota exhausted (429). Switching to OpenAI fallback...")
            # Immediately fall through to OpenAI
        else:
            logger.error(f"Gemini error: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error with Gemini: {e}")
        raise
    
    # Fallback to OpenAI if Gemini fails (for student projects - limited usage)
    if openai_client:
        if OPENAI_USAGE_TRACKER["total_requests"] < OPENAI_USAGE_TRACKER["max_openai_requests"]:
            try:
                logger.info(f"Using OpenAI fallback ({OPENAI_USAGE_TRACKER['total_requests']}/{OPENAI_USAGE_TRACKER['max_openai_requests']} allowed)...")
                response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                OPENAI_USAGE_TRACKER["total_requests"] += 1
                vec = response.data[0].embedding
                
                # Ensure dimension matches target
                n = len(vec)
                if n == TARGET_DIM:
                    return vec
                if n % TARGET_DIM == 0:
                    step = n // TARGET_DIM
                    return [sum(vec[i*step:(i+1)*step]) / step for i in range(TARGET_DIM)]
                stride = n / TARGET_DIM
                return [vec[int(i*stride)] for i in range(TARGET_DIM)]
                
            except Exception as e:
                logger.error(f"OpenAI embedding also failed: {e}")
                raise
        else:
            logger.error(f"OpenAI quota reached ({OPENAI_USAGE_TRACKER['max_openai_requests']} requests). Cannot proceed.")
            logger.error("This is a student project - OpenAI usage is limited to reduce costs.")
            raise Exception("Both Gemini and OpenAI embedding limits reached. Please try again later.")
    else:
        logger.error("No OpenAI API key configured and Gemini failed.")
        raise Exception("Embedding failed: Gemini quota exhausted and no OpenAI fallback configured.")


def load_csv_file(filepath: str) -> List[Dict[str, Any]]:
    """Load a CSV file and return rows as dictionaries."""
    rows = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        logger.info(f"Loaded {len(rows)} rows from {filepath}")
    except Exception as e:
        logger.error(f"Error loading CSV {filepath}: {e}")
        raise
    return rows


def create_chunks_from_csv(filepath: str, filename: str, chunk_size: int = 50) -> List[Dict[str, Any]]:
    """
    Create text chunks from CSV data.
    Groups rows into chunks for better semantic understanding.
    Larger chunks to stay within API quotas and reduce costs.
    """
    rows = load_csv_file(filepath)
    chunks = []
    
    # Group rows into chunks
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
    """
    Ingest all CSV files from the specified directory into Pinecone.
    Returns the total number of chunks uploaded.
    """
    
    if not os.path.exists(data_dir):
        logger.warning(f"Data directory {data_dir} not found. Creating it.")
        os.makedirs(data_dir)
    
    csv_files = [
        "prognosbarn_0_5_forecast.csv",
        "skollokaler_facilities.csv",
        "elever_students.csv",
        "personal_staff.csv",
        "ekonomi_economy.csv",
        "scenarios_skolstruktur.csv",
        "prognos_forvantade_entrants_F.csv"
    ]
    
    total_uploaded = 0
    
    for csv_file in csv_files:
        filepath = os.path.join(data_dir, csv_file)
        
        if not os.path.exists(filepath):
            logger.warning(f"File not found: {filepath}")
            continue
        
        logger.info(f"Processing {csv_file}...")
        
        chunks = create_chunks_from_csv(filepath, csv_file)
        
        # Upload chunks to Pinecone
        vectors = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{csv_file}_{idx}"
            logger.info(f"Embedding chunk {idx+1}/{len(chunks)} from {csv_file}...")
            vec = embed_text(chunk["text"])
            
            # Add small delay between requests to respect rate limits
            time.sleep(0.5)
            
            vectors.append({
                "id": chunk_id,
                "values": vec,
                "metadata": {
                    "chunk_text": chunk["text"],
                    "source_file": chunk["source_file"],
                    "start_row": chunk["start_row"],
                    "end_row": chunk["end_row"],
                }
            })
        
        # Upsert vectors to Pinecone
        try:
            index.upsert(
                namespace=PINECONE_NAMESPACE,
                vectors=vectors
            )
            logger.info(f"Uploaded {len(vectors)} chunks from {csv_file}")
            total_uploaded += len(vectors)
        except Exception as e:
            logger.error(f"Error uploading chunks from {csv_file}: {e}")
            raise
    
    logger.info(f"Total chunks uploaded: {total_uploaded}")
    logger.info(f"OpenAI usage: {OPENAI_USAGE_TRACKER['total_requests']}/{OPENAI_USAGE_TRACKER['max_openai_requests']} requests")
    return total_uploaded


if __name__ == "__main__":
    import sys
    
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    
    logger.info("Starting school data ingestion...")
    logger.info(f"OpenAI limit set to: {OPENAI_USAGE_TRACKER['max_openai_requests']} requests (student project)")
    total = ingest_school_data(data_dir)
    logger.info(f"School data ingestion completed. {total} chunks uploaded to Pinecone.")
    logger.info(f"Final OpenAI usage: {OPENAI_USAGE_TRACKER['total_requests']}/{OPENAI_USAGE_TRACKER['max_openai_requests']} requests")
