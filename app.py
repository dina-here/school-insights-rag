# app.py
import os
from pathlib import Path
from typing import List, Optional
import logging
import requests

from dotenv import load_dotenv
from datetime import datetime, timezone
from threading import Lock
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from google import genai
from google.genai import errors as genai_errors
from openai import OpenAI

# Use PostgreSQL backend instead of Pinecone
from rag_backend_postgres import get_school_analysis, build_sources_markdown, save_chat_log

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "system_prompt.txt")
# SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "../system_prompt.txt")

MODEL_ID = "gemini-2.0-flash"  # any chat-capable Gemini model you have access to 
OPENAI_MODEL = "gpt-5.2-chat-latest"  # OpenAI fallback model
SYSTEM_PROMPT = Path(SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")

client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = FastAPI(title="School Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Suppress logs for /health endpoint (Render health checks)
@app.middleware("http")
async def skip_health_logs(request: Request, call_next):
    response = await call_next(request)
    # Render's health checks spam logs; skip them
    if request.url.path == "/health":
        pass  # No logging for health endpoint
    return response

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Simple in-memory metrics
_metrics_lock = Lock()
METRICS = {
    "start_time": datetime.now(timezone.utc).isoformat(),
    "requests": 0,
    "errors": 0,
    "gemini_calls": 0,
    "openai_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}


class Message(BaseModel):
    role: str  # "user" or "model"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []
    
    @property
    def validated_message(self):
        """Enforce max 200 characters per message for token control"""
        return self.message[:200] if len(self.message) > 200 else self.message


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def root():
    """Serve the chat interface"""
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    """Health check endpoint for monitoring"""
    return {"status": "ok", "service": "School Analysis API"}


@app.get("/metrics")
def metrics():
    """Return simple runtime metrics for usage tracking"""
    with _metrics_lock:
        return METRICS.copy()


@app.get("/metrics.json")
def metrics_json():
    """Human-readable JSON metrics with uptime."""
    with _metrics_lock:
        snapshot = METRICS.copy()
    try:
        start_dt = datetime.fromisoformat(snapshot["start_time"])
    except Exception:
        start_dt = datetime.now(timezone.utc)
    uptime = (datetime.now(timezone.utc) - start_dt).total_seconds()
    snapshot["uptime_seconds"] = int(uptime)
    return snapshot


@app.get("/metrics.txt")
def metrics_text():
    """Plain-text human-friendly metrics with uptime."""
    with _metrics_lock:
        snapshot = METRICS.copy()
    try:
        start_dt = datetime.fromisoformat(snapshot["start_time"])
    except Exception:
        start_dt = datetime.now(timezone.utc)
    uptime = int((datetime.now(timezone.utc) - start_dt).total_seconds())
    lines = [
        f"start_time: {snapshot['start_time']}",
        f"uptime_seconds: {uptime}",
        f"requests: {snapshot['requests']}",
        f"errors: {snapshot['errors']}",
        f"gemini_calls: {snapshot['gemini_calls']}",
        f"openai_calls: {snapshot['openai_calls']}",
        f"prompt_tokens: {snapshot['prompt_tokens']}",
        f"completion_tokens: {snapshot['completion_tokens']}",
        f"total_tokens: {snapshot['total_tokens']}",
    ]
    body = "\n".join(lines) + "\n"
    return PlainTextResponse(content=body)


@app.post("/metrics/reset")
def metrics_reset(key: Optional[str] = None):
    """Reset counters; require `METRICS_RESET_KEY` if configured."""
    expected = os.getenv("METRICS_RESET_KEY")
    if expected:
        if not key or key != expected:
            raise HTTPException(status_code=403, detail="Forbidden")
    now = datetime.now(timezone.utc).isoformat()
    with _metrics_lock:
        METRICS.update({
            "start_time": now,
            "requests": 0,
            "errors": 0,
            "gemini_calls": 0,
            "openai_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        })
    return {"status": "reset", "start_time": now}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Input validation: limit to 200 chars to control tokens
    message = req.validated_message
    with _metrics_lock:
        METRICS["requests"] += 1
    
    # 1) Call the "get_school_analysis tool" to retrieve relevant school data
    # Use top_k=40 to cover larger files and diverse sources
    docs = get_school_analysis(message, top_k=40)
    
    # Concatenate retrieved snippets - increased limit for complete data
    context = "\n\n".join(f"- {d['text']}" for d in docs)[:35000]
    
    sources_md = build_sources_markdown(docs)

    # 2) Build instruction that includes:
    #    - the original system prompt from system_prompt.txt
    #    - the current retrieved school data snippets ("source data")
    system_and_context = (
        SYSTEM_PROMPT
        + "\n\n### Source data from school analysis:\n"
        + context
    )

    # 3) Convert into Gemini-style contents
    contents = [{"role": "user", "parts": [{"text": system_and_context}]}]
    for m in req.history:
        contents.append({"role": m.role, "parts": [{"text": m.content}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    answer = None
    
    # Try Gemini first
    try:
        result = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
        )
        answer = result.text.strip()
        # Collect Gemini usage if available
        try:
            usage = getattr(result, "usage_metadata", None)
            prompt_t = getattr(usage, "prompt_token_count", 0) if usage else 0
            completion_t = getattr(usage, "candidates_token_count", 0) if usage else 0
            total_t = getattr(usage, "total_token_count", 0) if usage else (prompt_t + completion_t)
            with _metrics_lock:
                METRICS["gemini_calls"] += 1
                METRICS["prompt_tokens"] += int(prompt_t or 0)
                METRICS["completion_tokens"] += int(completion_t or 0)
                METRICS["total_tokens"] += int(total_t or 0)
            logger.info(f"Gemini tokens: prompt={prompt_t}, completion={completion_t}, total={total_t}")
        except Exception as _:
            # Non-fatal if usage not available
            pass
    except genai_errors.ClientError as e:
        # Log Gemini error
        logger.error(f"Gemini error: {e}")
        # Fallback to OpenAI on Gemini errors when available
        if openai_client:
            try:
                # Convert history to OpenAI format
                openai_messages = [
                    {"role": "system", "content": system_and_context}
                ]
                for m in req.history:
                    openai_messages.append({
                        "role": "assistant" if m.role == "model" else m.role,
                        "content": m.content
                    })
                openai_messages.append({"role": "user", "content": message})
                
                # Call OpenAI with gpt-5.2-chat-latest
                response = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=openai_messages,
                    max_completion_tokens=1500,
                )
                answer = response.choices[0].message.content.strip()
                # Collect OpenAI usage
                try:
                    usage = getattr(response, "usage", None)
                    prompt_t = getattr(usage, "prompt_tokens", None)
                    completion_t = getattr(usage, "completion_tokens", None)
                    total_t = getattr(usage, "total_tokens", None)
                    with _metrics_lock:
                        METRICS["openai_calls"] += 1
                        METRICS["prompt_tokens"] += int(prompt_t or 0)
                        METRICS["completion_tokens"] += int(completion_t or 0)
                        METRICS["total_tokens"] += int(total_t or 0)
                    logger.info(f"OpenAI tokens: prompt={prompt_t}, completion={completion_t}, total={total_t}")
                except Exception:
                    with _metrics_lock:
                        METRICS["openai_calls"] += 1
            except Exception as oe:
                # Log OpenAI error
                logger.error(f"OpenAI error: {oe}")
                with _metrics_lock:
                    METRICS["errors"] += 1
                answer = "I'm sorry, I can't answer that. Please contact HR"
        else:
            # No OpenAI configured
            logger.warning("OpenAI client not configured, using fallback")
            with _metrics_lock:
                METRICS["errors"] += 1
            answer = "I'm sorry, I can't answer that. Please contact HR"

    # 4) Append our own “Sources” footer (the prompt also asks for this style)
    # 4) Check if answer is empty (Gemini sometimes returns empty on complex prompts)
    if not answer or not answer.strip():
        logger.warning("Empty answer from model, using data summary")
        # Build a basic summary from retrieved docs
        answer = "Baserat på tillgänglig data:\n" + "\n".join([f"• {d['text'][:100]}..." for d in docs[:3]])
    
    # 5) Append our own "Sources" footer
    answer_with_sources = answer.strip() + "\n\n" + sources_md
    
    # 6) Save to chat logs for analytics
    try:
        source_files = ",".join([d.get("file", "unknown") for d in docs])
        save_chat_log(message, answer_with_sources, source_files)
    except Exception as e:
        logger.warning(f"Failed to save chat log: {e}")

    return ChatResponse(reply=answer_with_sources)
