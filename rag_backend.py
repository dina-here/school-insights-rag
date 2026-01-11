# rag_backend.py
import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from google import genai
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

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
    """Retrieve relevant school analysis data from Pinecone."""
    vec = embed_query(query)
    result = index.query(
        namespace=PINECONE_NAMESPACE,
        vector=vec,
        top_k=top_k,
        include_metadata=True,
        include_values=False,
    )

    docs = []
    for m in result["matches"]:
        md = m.get("metadata", {})
        docs.append(
            {
                "score": m.get("score"),
                "text": md.get("chunk_text", ""),
                "file": md.get("source_file", ""),
                "url": md.get("url"),
            }
        )
    return docs


def build_sources_markdown(docs: List[Dict[str, Any]]) -> str:
    """Format like the example in system_prompt.txt."""
    lines = ["Sources:"]
    # make each file appear only once
    seen = {}
    for d in docs:
        file = d["file"] or "Document"
        if file in seen:
            continue
        seen[file] = True
        url = d.get("url") or file
        lines.append(f"- ^1 [{file}]({url})")
    return "\n".join(lines)
