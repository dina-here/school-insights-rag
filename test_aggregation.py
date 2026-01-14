#!/usr/bin/env python3
import psycopg2
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    exit(1)

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("\n=== Testing substring parsing ===")
    query = """
        SELECT chunk_text
        FROM school_embeddings
        WHERE source_file = 'elever_students.csv'
        LIMIT 1;
    """
    cur.execute(query)
    result = cur.fetchone()
    if result:
        print(f"Sample chunk text:\n{result[0][:300]}\n")
    
    print("\n=== Testing aggregation query for Hisingen 2025 ===")
    # Simplified version - just get the data directly
    query = """
        SELECT 
            substring(chunk_text from 'School: (\w+)') as school,
            CAST(substring(chunk_text from 'Year: (\d+)') AS INT) as year,
            CAST(substring(chunk_text from 'Enrolled_Students: (\d+)') AS INT) as enrolled
        FROM school_embeddings
        WHERE source_file = 'elever_students.csv'
        LIMIT 5;
    """
    cur.execute(query)
    results = cur.fetchall()
    print("Sample rows from elever_students.csv:")
    for row in results:
        print(f"  School: {row[0]}, Year: {row[1]}, Enrolled: {row[2]}")
    
    cur.close()
    conn.close()
    print("\nConnection test successful!")
    
except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc()
