# ingest_hr_docs.py
import sys
import os
import uuid
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from google import genai
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from pypdf import PdfReader

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX_HOST = os.environ["PINECONE_INDEX_HOST"]
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "hr")
DOCS_DIR = os.getenv("DOCS_DIR", "documents")
GITHUB_DOC_BASE_URL = os.getenv("GITHUB_DOC_BASE_URL", "")

# DOCS_DIR = os.getenv("DOCS_DIR", "../documents")
# GITHUB_DOC_BASE_URL = os.getenv("GITHUB_DOC_BASE_URL")

client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_INDEX_HOST)  # host is your hr-… Pinecone endpoint
TARGET_DIM = int(os.getenv("EMBED_DIM", "768"))


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages)
    else:
        return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> List[str]:
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        chunks.append(text[start:end])
        if end == n:
            break  # avoid negative start when text length < overlap
        start = max(end - overlap, start + 1)
    return chunks


def embed(text: str) -> List[float]:
    """Embed text using Gemini, with OpenAI fallback if quota exceeded."""
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
    # Downsample to match Pinecone index dim for demo
    # Average-pool contiguous blocks when divisible
    if n % TARGET_DIM == 0:
        step = n // TARGET_DIM
        return [sum(vec[i*step:(i+1)*step]) / step for i in range(TARGET_DIM)]
    # Fallback: stride sampling without extra deps
    stride = n / TARGET_DIM
    return [vec[int(i*stride)] for i in range(TARGET_DIM)]


def ingest_directory():
    base = Path(DOCS_DIR)
    files = list(base.glob("*"))

    print(f"Found {len(files)} docs in {base.resolve()}")

    for fp in files:
        if not fp.is_file():
            continue

        text = extract_text(fp)
        chunks = chunk_text(text)
        if not chunks:
            continue

        vectors = []
        for i, chunk in enumerate(chunks):
            if "--dry-run" not in sys.argv:
                vec = embed(chunk)
            else:
                vec = [0.0] * 768  # dummy vector for dry-run
            rid = f"{fp.name}#{i}-{uuid.uuid4().hex[:8]}"

            url = None
            if GITHUB_DOC_BASE_URL:
                # simple best-effort URL (spaces remain as in example citation)
                url = GITHUB_DOC_BASE_URL.rstrip("/") + "/" + fp.name

            metadata = {
                "source_file": fp.name,
                "chunk_index": i,
                "chunk_text": chunk,
            }
            if url:
                metadata["url"] = url

            vectors.append(
                {
                    "id": rid,
                    "values": vec,
                    "metadata": metadata,
                }
            )

        if "--dry-run" in sys.argv:
            print(f"[DRY-RUN] Would ingest {len(vectors)} chunks from {fp.name}")
        else:
            index.upsert(
                namespace=PINECONE_NAMESPACE,
                vectors=vectors,
            )
            print(f"Ingested {len(vectors)} chunks from {fp.name}")


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        print("=== DRY RUN MODE ===\nNo Pinecone connection, no upsert.\n")
    ingest_directory()
