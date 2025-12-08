from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from .schemas import ChatRequest, ChatResponse
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator
import platform
import openai
import asyncio
import time
import json
from src.config import settings
from src.embeddings import get_embedding_dimension
from src.logger import get_logger
from src.orchestration.retriever import DataRetriever
from src.llm.response_generator import ResponseGenerator

logger = get_logger(__name__)

# Path to test client
TEST_CLIENT_DIR = Path(__file__).parent.parent.parent / "test_client"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Journalyst AI Assistant API...")
    logger.info(f"Test client available at: http://localhost:8000/")
    yield
    logger.info("Shutting down Journalyst AI Assistant API...")

app = FastAPI(title="Journalyst AI Assistant", version="0.1.0", docs_url="/docs", lifespan=lifespan)

# CORS middleware - allow cross-origin requests from test client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins like ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for test client (CSS, JS)
if TEST_CLIENT_DIR.exists():
    app.mount("/static", StaticFiles(directory=TEST_CLIENT_DIR), name="static")


async def generate_stream_response(
    request: ChatRequest,
    retriever: DataRetriever,
    retrieved_data: dict,
    start_time: float,
    request_id: str = "unknown"
) -> AsyncGenerator[str, None]:
    """
    Async generator for Server-Sent Events (SSE) streaming.
    Yields SSE-formatted events with text chunks.
    """
    try:
        # Send start event with metadata
        start_event = {
            "event": "start",
            "data": {
                "request_id": request_id,
                "query_type": retriever.query_analysis.get("query_type") if retriever.query_analysis else "unknown"
            }
        }
        yield f"event: start\ndata: {json.dumps(start_event['data'])}\n\n"
        
        # Send retrieved data
        data_event = {"trade_data": retrieved_data.get("trade_data", []), "journal_data": retrieved_data.get("journal_data", [])}
        yield f"event: data\ndata: {json.dumps(data_event)}\n\n"
        
        # Stream LLM response
        llm_start = time.perf_counter()
        generator = ResponseGenerator()
        context_str = f"Retrieved Data: {retrieved_data}"
        
        full_response = ""
        chunk_count = 0
        for chunk in generator.generate_response_stream(
            user_query=request.query,
            context=context_str,
            user_name=request.user_name
        ):
            full_response += chunk
            chunk_count += 1
            # Send each text chunk
            yield f"event: chunk\ndata: {json.dumps({'text': chunk})}\n\n"
            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.01)
        
        llm_duration = (time.perf_counter() - llm_start) * 1000
        
        # Send done event with final metadata
        total_duration = (time.perf_counter() - start_time) * 1000
        done_event = {
            "request_id": request_id,
            "duration_ms": total_duration,
            "llm_ms": llm_duration,
            "response_length": len(full_response),
            "chunks": chunk_count,
            "query_type": retriever.query_analysis.get("query_type") if retriever.query_analysis else "unknown"
        }
        yield f"event: done\ndata: {json.dumps(done_event)}\n\n"
        
        logger.info(f"[API] STREAM COMPLETE | id={request_id} | llm={llm_duration:.0f}ms | total={total_duration:.0f}ms | chunks={chunk_count}")
        logger.info(f"[API] ════════════════════════════════════════════════════════")
        
    except Exception as e:
        duration = (time.perf_counter() - start_time) * 1000
        logger.error(f"[API] STREAM FAILED | id={request_id} | duration={duration:.0f}ms | error={e}")
        logger.info(f"[API] ════════════════════════════════════════════════════════")
        error_event = {"error": str(e)}
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint supporting both streaming and non-streaming responses.
    Set request.stream=true for SSE streaming.
    """
    import uuid
    request_id = str(uuid.uuid4())[:8]
    start_time = time.perf_counter()
    query_preview = request.query[:60] + "..." if len(request.query) > 60 else request.query
    
    logger.info(f"[API] ════════════════════════════════════════════════════════")
    logger.info(f"[API] REQUEST START | id={request_id} | user={request.user_id} | stream={request.stream}")
    logger.info(f"[API] Query: '{query_preview}'")

    try:
        # 1. Retrieve Data (always done first, before streaming)
        retriever_start = time.perf_counter()
        retriever = DataRetriever(user_id=request.user_id)
        retrieved_data = retriever.retrieve_data(request.query)
        retriever_duration = (time.perf_counter() - retriever_start) * 1000
        
        trade_count = len(retrieved_data.get("trades", []))
        journal_count = len(retrieved_data.get("journals", []))
        logger.info(f"[API] Data retrieved | trades={trade_count} | journals={journal_count} | duration={retriever_duration:.0f}ms")
        
        # 2. Handle streaming vs non-streaming
        if request.stream:
            logger.info(f"[API] Starting SSE stream...")
            return StreamingResponse(
                generate_stream_response(request, retriever, retrieved_data, start_time, request_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # Disable nginx buffering
                }
            )
        
        # Non-streaming response (original behavior)
        llm_start = time.perf_counter()
        generator = ResponseGenerator()
        context_str = f"Retrieved Data: {retrieved_data}"
        
        response_text = generator.generate_response(
            user_query=request.query,
            context=context_str,
            user_name=request.user_name
        )
        llm_duration = (time.perf_counter() - llm_start) * 1000

        total_duration = (time.perf_counter() - start_time) * 1000
        
        logger.info(f"[API] REQUEST COMPLETE | id={request_id} | retrieval={retriever_duration:.0f}ms | llm={llm_duration:.0f}ms | total={total_duration:.0f}ms")
        logger.info(f"[API] ════════════════════════════════════════════════════════")

        return ChatResponse(
            response=response_text,
            data=retrieved_data,
            metadata={
                "request_id": request_id,
                "duration_ms": total_duration,
                "retrieval_ms": retriever_duration,
                "llm_ms": llm_duration,
                "query_type": retriever.query_analysis.get("query_type") if retriever.query_analysis else "unknown"
            }
        )

    except Exception as e:
        duration = (time.perf_counter() - start_time) * 1000
        logger.error(f"[API] REQUEST FAILED | id={request_id} | duration={duration:.0f}ms | error={e}")
        logger.info(f"[API] ════════════════════════════════════════════════════════")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    logger.debug("Health check requested")
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat() + "Z",
        "environment": settings.environment,
        "debug": settings.debug,
        "python_version": platform.python_version(),
        "openai_version": getattr(openai, "__version__", "unknown"),
        "postgres": {"rw_dsn_masked": mask_dsn(settings.postgres_rw_dsn), "ro_dsn_masked": mask_dsn(settings.postgres_ro_dsn)},
        "redis_url": settings.redis_url,
        "qdrant_url": settings.qdrant_url,
        "models": {
            "router": settings.router_model,
            "analysis": settings.analysis_model,
            "embedding": settings.embedding_model,
            "embedding_provider": settings.embedding_provider,
            "embedding_dimension": get_embedding_dimension(),
            "reasoning": settings.reasoning_model,
        }
    }


def mask_dsn(dsn: str) -> str:
    # Simple masking: hide password between ':' and '@'
    if ":" in dsn and "@" in dsn:
        pre, rest = dsn.split(":", 1)
        pwd_and_host = rest.split("@", 1)
        if len(pwd_and_host) == 2:
            return pre + ":***@" + pwd_and_host[1]
    return dsn


# Serve test client UI
@app.get("/")
async def serve_test_client():
    """Serve the test client HTML page."""
    index_file = TEST_CLIENT_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Journalyst AI Assistant API running", "docs": "/docs", "health": "/health"}
