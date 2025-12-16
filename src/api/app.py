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
from src.cache.session import SessionManager

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
        
        # Build context with session history
        session_mgr = SessionManager()
        session = session_mgr.get_session(request.session_id) if request.session_id else None
        history_text = ""
        if session and session.get("messages"):
            history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in session["messages"]])
            history_text = f"Conversation History:\n{history_text}\n\n"
        
        context_str = f"{history_text}Retrieved Data: {retrieved_data}"
        
        # Extract date context from retriever for prompt enrichment
        date_period_context = None
        if retriever.date_context:
            _, _, date_context_str = retriever.date_context
            date_period_context = date_context_str
        
        current_date = retriever.current_date.strftime("%B %d, %Y")
        
        full_response = ""
        chunk_count = 0
        for chunk in generator.generate_response_stream(
            user_query=request.query,
            context=context_str,
            user_name=request.user_name,
            current_date=current_date,
            date_period_context=date_period_context
        ):
            full_response += chunk
            chunk_count += 1
            # Send each text chunk
            yield f"event: chunk\ndata: {json.dumps({'text': chunk})}\n\n"
            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.01)
        
        # Save assistant response to session
        if request.session_id:
            session_mgr.add_message(request.session_id, "assistant", full_response)
        
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


async def _generate_out_of_domain_response(
    response_text: str,
    start_time: float,
    request_id: str = "unknown"
) -> AsyncGenerator[str, None]:
    """
    Async generator for out-of-domain query rejection (SSE streaming).
    Yields a polite rejection message.
    """
    try:
        # Send start event
        start_event = {
            "event": "start",
            "data": {
                "request_id": request_id,
                "query_type": "out_of_domain",
                "status": "rejected"
            }
        }
        yield f"event: start\ndata: {json.dumps(start_event['data'])}\n\n"
        
        # Send data event (empty for out-of-domain)
        data_event = {"trade_data": [], "journal_data": []}
        yield f"event: data\ndata: {json.dumps(data_event)}\n\n"
        
        # Send response as single chunk
        yield f"event: chunk\ndata: {json.dumps({'text': response_text})}\n\n"
        
        # Send done event
        total_duration = (time.perf_counter() - start_time) * 1000
        done_event = {
            "request_id": request_id,
            "duration_ms": total_duration,
            "response_length": len(response_text),
            "chunks": 1,
            "query_type": "out_of_domain",
            "status": "rejected"
        }
        yield f"event: done\ndata: {json.dumps(done_event)}\n\n"
        
        logger.info(f"[API] OUT-OF-DOMAIN STREAM COMPLETE | id={request_id} | total={total_duration:.0f}ms")
        
    except Exception as e:
        duration = (time.perf_counter() - start_time) * 1000
        logger.error(f"[API] OUT-OF-DOMAIN STREAM FAILED | id={request_id} | duration={duration:.0f}ms | error={e}")
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
        # 0. Session management - create session if needed and store user message
        session_mgr = SessionManager()
        if request.session_id:
            session = session_mgr.get_session(request.session_id)
            if not session:
                session_mgr.create_session(request.session_id, str(request.user_id))
            session_mgr.add_message(request.session_id, "user", request.query)
        else:
            # Generate session_id if not provided
            request.session_id = str(uuid.uuid4())
            session_mgr.create_session(request.session_id, str(request.user_id))
            session_mgr.add_message(request.session_id, "user", request.query)
            logger.info(f"[API] Generated new session_id: {request.session_id[:8]}...")
        
        # 1. Retrieve Data (always done first, before streaming)
        retriever_start = time.perf_counter()
        retriever = DataRetriever(user_id=request.user_id)
        retrieved_data = retriever.retrieve_data(request.query)
        retriever_duration = (time.perf_counter() - retriever_start) * 1000
        
        trade_count = len(retrieved_data.get("trades", []))
        journal_count = len(retrieved_data.get("journals", []))
        logger.info(f"[API] Data retrieved | trades={trade_count} | journals={journal_count} | duration={retriever_duration:.0f}ms")
        
        # 2. Check if query is in-domain (reject out-of-domain queries)
        is_in_domain = (retriever.query_analysis or {}).get("is_in_domain", True)
        if not is_in_domain:
            out_of_domain_response = "I'm specifically designed to help with trading analysis and performance insights. Your question is outside my area of expertise. Please ask me about your trades, strategies, performance metrics, or trading psychology."
            logger.info(f"[API] OUT-OF-DOMAIN query rejected | query_type={(retriever.query_analysis or {}).get('query_type', 'unknown')}")
            
            if request.stream:
                return StreamingResponse(
                    _generate_out_of_domain_response(out_of_domain_response, start_time, request_id),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no"
                    }
                )
            else:
                return ChatResponse(
                    response=out_of_domain_response,
                    data={},
                    metadata={
                        "request_id": request_id,
                        "duration_ms": (time.perf_counter() - start_time) * 1000,
                        "query_type": "out_of_domain",
                        "status": "rejected"
                    }
                )
        
        # 3. Handle streaming vs non-streaming
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
        
        # Build context with session history
        session = session_mgr.get_session(request.session_id) if request.session_id else None
        history_text = ""
        if session and session.get("messages"):
            history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in session["messages"]])
            history_text = f"Conversation History:\n{history_text}\n\n"
        
        context_str = f"{history_text}Retrieved Data: {retrieved_data}"
        
        # Extract date context from retriever for prompt enrichment
        date_period_context = None
        if retriever.date_context:
            _, _, date_context_str = retriever.date_context
            date_period_context = date_context_str
        
        current_date = retriever.current_date.strftime("%B %d, %Y")
        
        response_text = generator.generate_response(
            user_query=request.query,
            context=context_str,
            user_name=request.user_name,
            current_date=current_date,
            date_period_context=date_period_context
        )
        llm_duration = (time.perf_counter() - llm_start) * 1000
        
        # Save assistant response to session
        if request.session_id:
            session_mgr.add_message(request.session_id, "assistant", response_text)

        total_duration = (time.perf_counter() - start_time) * 1000
        
        logger.info(f"[API] REQUEST COMPLETE | id={request_id} | retrieval={retriever_duration:.0f}ms | llm={llm_duration:.0f}ms | total={total_duration:.0f}ms")
        logger.info(f"[API] ════════════════════════════════════════════════════════")

        return ChatResponse(
            response=response_text,
            data=retrieved_data,
            metadata={
                "request_id": request_id,
                "session_id": request.session_id,
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
