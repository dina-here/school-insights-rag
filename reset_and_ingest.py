#!/usr/bin/env python3
"""
Reset and re-ingest all CSV data into Render PostgreSQL.
This TRUNCATES the school_embeddings table and then ingests fresh data.

Usage:
  python reset_and_ingest.py <path-to-csv-directory>
  python reset_and_ingest.py data/new_csvs
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv
from ingest_school_data_postgres import ingest_school_data

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in .env")
    print("Add your Render PostgreSQL connection string to .env:")
    print("DATABASE_URL=postgresql://user:password@host/dbname")
    sys.exit(1)

def reset_embeddings():
    """Truncate the school_embeddings table."""
    try:
        print("🗑️  Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("🗑️  Truncating school_embeddings table...")
        cur.execute("TRUNCATE TABLE school_embeddings;")
        conn.commit()
        
        cur.close()
        conn.close()
        
        print("✅ Old data cleared successfully!\n")
        return True
        
    except Exception as e:
        print(f"❌ Error truncating table: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reset_and_ingest.py <path-to-csv-directory>")
        print("Example: python reset_and_ingest.py data")
        print("Example: python reset_and_ingest.py C:\\Data\\new_school_csvs")
        sys.exit(1)
    
    csv_directory = sys.argv[1]
    
    if not os.path.exists(csv_directory):
        print(f"❌ ERROR: Directory not found: {csv_directory}")
        sys.exit(1)
    
    print("=" * 60)
    print("FULL RESET AND RE-INGEST")
    print("=" * 60)
    print(f"CSV Directory: {csv_directory}")
    print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'PostgreSQL'}")
    print("=" * 60)
    print()
    
    # Step 1: Clear old data
    if not reset_embeddings():
        print("\n❌ Failed to reset. Aborting.")
        sys.exit(1)
    
    # Step 2: Ingest new data
    print("📥 Starting fresh ingestion...")
    print()
    
    try:
        total = ingest_school_data(csv_directory)
        print()
        print("=" * 60)
        print(f"✅ COMPLETE! {total} chunks uploaded.")
        print("=" * 60)
        print()
        print("You can now test queries like:")
        print('  - "elevantal på Hisingen 2025"')
        print('  - "Hur många elever i Centrum?"')
        print()
        
    except Exception as e:
        print(f"\n❌ Ingestion failed: {e}")
        sys.exit(1)
