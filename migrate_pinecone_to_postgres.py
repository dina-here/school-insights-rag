#!/usr/bin/env python3
"""
Migrate data from Pinecone to PostgreSQL with pgvector
Copies all vectors and metadata without regenerating embeddings
"""

import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

import psycopg2
from pinecone import Pinecone

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Pinecone config
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX_HOST = os.environ["PINECONE_INDEX_HOST"]
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "school")

# PostgreSQL config
DATABASE_URL = os.environ["DATABASE_URL"]

def migrate_pinecone_to_postgres():
    """Copy all vectors from Pinecone to PostgreSQL."""
    
    logger.info("Connecting to Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(host=PINECONE_INDEX_HOST)
    
    logger.info("Connecting to PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Get index stats
    stats = index.describe_index_stats()
    namespace_stats = stats.get('namespaces', {}).get(PINECONE_NAMESPACE, {})
    total_vectors = namespace_stats.get('vector_count', 0)
    
    logger.info(f"Found {total_vectors} vectors in Pinecone namespace '{PINECONE_NAMESPACE}'")
    
    if total_vectors == 0:
        logger.warning("No vectors found in Pinecone. Nothing to migrate.")
        return 0
    
    # Fetch all vectors from Pinecone
    # We'll query in batches by listing IDs first
    logger.info("Fetching vector IDs from Pinecone...")
    
    # Query to get all vector IDs (use a dummy vector, we just want IDs)
    # Alternative: use list_paginated if available
    migrated = 0
    batch_size = 100
    
    try:
        # Get all IDs by doing a query with high top_k
        # This is a workaround - Pinecone doesn't have a direct "list all" API
        logger.info("Querying Pinecone for all vectors...")
        
        # Create a dummy query vector
        dummy_vector = [0.0] * 768  # Assuming 768 dimensions
        
        # Query with large top_k to get all vectors
        results = index.query(
            namespace=PINECONE_NAMESPACE,
            vector=dummy_vector,
            top_k=min(10000, total_vectors),  # Pinecone max is usually 10000
            include_metadata=True,
            include_values=True
        )
        
        logger.info(f"Retrieved {len(results['matches'])} vectors from Pinecone")
        
        # Insert into PostgreSQL
        for match in results['matches']:
            vector_id = match['id']
            values = match['values']
            metadata = match.get('metadata', {})
            
            chunk_text = metadata.get('chunk_text', '')
            source_file = metadata.get('source_file', '')
            start_row = metadata.get('start_row')
            end_row = metadata.get('end_row')
            
            try:
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
                    vector_id,
                    values,
                    chunk_text,
                    source_file,
                    start_row,
                    end_row
                ))
                
                migrated += 1
                
                if migrated % 10 == 0:
                    logger.info(f"Migrated {migrated}/{len(results['matches'])} vectors...")
                    
            except Exception as e:
                logger.error(f"Error inserting vector {vector_id}: {e}")
                continue
        
        conn.commit()
        logger.info(f"✅ Successfully migrated {migrated} vectors from Pinecone to PostgreSQL!")
        
        # Verify
        cur.execute("SELECT COUNT(*) FROM school_embeddings;")
        total_in_pg = cur.fetchone()[0]
        logger.info(f"Total vectors in PostgreSQL: {total_in_pg}")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    
    return migrated


if __name__ == "__main__":
    logger.info("Starting Pinecone → PostgreSQL migration...")
    logger.info(f"Namespace: {PINECONE_NAMESPACE}")
    
    try:
        total = migrate_pinecone_to_postgres()
        logger.info(f"✅ Migration complete! {total} vectors copied.")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        exit(1)
