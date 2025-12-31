from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import platform
import time
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import openai
from src.config import settings
from src.embeddings import get_embedding_dimension
from src.logger import get_logger
from src.orchestration.retriever import DataRetriever
from src.orchestration.router import QueryRouter
from src.llm.response_generator import ResponseGenerator
from src.cache.session import SessionManager
from .schemas import ChatRequest, ChatResponse
from .helpers import (
    PostgreSQLEncoder,
    mask_dsn,
    build_compact_context,
    build_history_text,
    generate_stream_response,
    generate_out_of_domain_response,
    OUT_OF_DOMAIN_RESPONSE,
)

logger = get_logger(__name__)

# Path to test client
TEST_CLIENT_DIR = Path(__file__).parent.parent.parent / "test_client"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
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

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint supporting both streaming and non-streaming responses.
    Set request.stream=true for SSE streaming.
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.perf_counter()
    query_preview = request.query[:60] + "..." if len(request.query) > 60 else request.query
    
    logger.info("[API] " + "="*60)
    logger.info(f"[API] REQUEST START | id={request_id} | user={request.user_id} | stream={request.stream} | session_id={request.session_id[:8] + '...' if request.session_id else 'none'}")
    logger.info(f"[API] Query: '{query_preview}'")

    try:
        # Session management - create session if needed
        logger.info(f"[API] Managing session...")
        session_mgr = SessionManager()
        if request.session_id:
            logger.info(f"[API] Using provided session_id: {request.session_id[:8]}...")
            session = session_mgr.get_session(request.session_id)
            if not session:
                logger.info(f"[API] Session not found for provided session_id: {request.session_id[:8]}... Creating new session.")
                session_mgr.create_session(request.session_id, str(request.user_id))
        else:
            # Generate session_id if not provided
            request.session_id = str(uuid.uuid4())
            session_mgr.create_session(request.session_id, str(request.user_id))
            logger.info(f"[API] Generated new session_id: {request.session_id[:8]}...")
        
        # Detect if this is a follow-up query BEFORE adding current message
        logger.info(f"[API] Checking for follow-up query...")
        session = session_mgr.get_session(request.session_id)
        messages = session.get("messages", []) if session else []
        previous_query = None
        is_followup = False
        followup_ref = None
        anchor_scope = None
        
        # Look for the last user message in the existing conversation
        if len(messages) >= 2:
            # Find last user message (messages alternate: user, assistant, user, assistant...)
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    previous_query = messages[i].get("content")
                    logger.info(f"[API] Found previous query: '{previous_query[:50]}...'")
                    break
            
            if previous_query:
                router = QueryRouter()
                followup_detection = router.detect_followup(request.query, previous_query)
                is_followup = followup_detection.get("is_followup", False)
                confidence = followup_detection.get("confidence", 0.0)
                logger.info(f"[API] Follow-up detection result | is_followup={is_followup} | confidence={confidence:.2f}")
                
                if is_followup and confidence >= 0.6:
                    # Get the last query context for scope reference
                    contexts = session.get("query_contexts", []) if session else []
                    followup_ref = str(len(contexts) - 1) if contexts else None
                    
                    # Build anchor_scope from prior query IDs
                    if followup_ref is not None:
                        anchor_scope = session_mgr.get_query_scope(request.session_id, int(followup_ref))
                        if anchor_scope:
                            trade_ids_preview = anchor_scope.get("trade_ids", [])[:5]
                            journal_ids_preview = anchor_scope.get("journal_ids", [])[:5]
                            logger.info(f"[API] Anchor scope retrieved | trade_ids={len(anchor_scope.get('trade_ids', []))} {trade_ids_preview}... | journal_ids={len(anchor_scope.get('journal_ids', []))} {journal_ids_preview}...")
                        else:
                            logger.warning(f"[API] Could not retrieve anchor scope for followup_ref={followup_ref}")
        
        # Now add the current user message to session
        session_mgr.add_message(request.session_id, "user", request.query)

        logger.info(f"[API] is_followup={is_followup} | followup_ref={followup_ref}")
        
        # 1. Retrieve Data (pass anchor_scope for follow-ups)
        retriever_start = time.perf_counter()
        retriever = DataRetriever(user_id=request.user_id)
        retrieved_data = retriever.retrieve_data(request.query, anchor_scope=anchor_scope)
        retriever_duration = (time.perf_counter() - retriever_start) * 1000
        
        trade_count = len(retrieved_data.get("trades", []))
        journal_count = len(retrieved_data.get("journals", []))
        logger.info(f"[API] Data retrieved | trades={trade_count} | journals={journal_count} | duration={retriever_duration:.0f}ms")
        
        # 1.5 Store query context for future follow-ups (pass date_range from retriever)
        date_range = retriever.date_context[:2] if retriever.date_context else None
        session_mgr.add_query_context(
            request.session_id,
            request.query,
            retrieved_data,
            is_followup=is_followup,
            followup_ref=anchor_scope,
            date_range=date_range
        )

        # Check if query is in-domain (reject out-of-domain queries)
        logger.info(f"[API] Checking if query is in-domain...")
        is_in_domain = (retriever.query_analysis or {}).get("is_in_domain", True)
        if not is_in_domain:
            logger.info(f"[API] OUT-OF-DOMAIN query rejected | query_type={(retriever.query_analysis or {}).get('query_type', 'unknown')}")
            
            if request.stream:
                return StreamingResponse(
                    generate_out_of_domain_response(OUT_OF_DOMAIN_RESPONSE, start_time, request_id),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no"
                    }
                )
            else:
                return ChatResponse(
                    response=OUT_OF_DOMAIN_RESPONSE,
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
            # For follow-ups, use anchor IDs; otherwise no scope constraint
            trade_scope_for_llm = anchor_scope.get("trade_ids", []) if (is_followup and anchor_scope) else None
            return StreamingResponse(
                generate_stream_response(
                    request, 
                    retriever, 
                    retrieved_data, 
                    start_time, 
                    request_id,
                    is_followup=is_followup,
                    trade_scope=trade_scope_for_llm,
                    anchor_scope=anchor_scope
                ),
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
        history_text = build_history_text(session, request.user_id, request.query)
        
        # Build compact context summary
        compact_context = build_compact_context(retrieved_data, is_followup, anchor_scope)
        context_str = f"{history_text}{compact_context}"
        
        # Extract date context from retriever for prompt enrichment
        date_period_context = None
        if retriever.date_context:
            _, _, date_context_str = retriever.date_context
            date_period_context = date_context_str
        
        current_date = retriever.current_date.strftime("%B %d, %Y")
        
        # For follow-ups, use anchor IDs; otherwise no scope constraint
        trade_scope_for_llm = anchor_scope.get("trade_ids", []) if (is_followup and anchor_scope) else None
        
        response_text = generator.generate_response(
            user_query=request.query,
            context=context_str,
            user_name=request.user_name,
            current_date=current_date,
            date_period_context=date_period_context,
            is_followup=is_followup,
            trade_scope=trade_scope_for_llm
        )
        llm_duration = (time.perf_counter() - llm_start) * 1000
        
        # Save assistant response to session
        if request.session_id:
            session_mgr.add_message(request.session_id, "assistant", response_text)

        total_duration = (time.perf_counter() - start_time) * 1000
        
        logger.info(f"[API] REQUEST COMPLETE | id={request_id} | retrieval={retriever_duration:.0f}ms | llm={llm_duration:.0f}ms | total={total_duration:.0f}ms")
        logger.info("[API] " + "="*60)

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
        logger.exception(f"[API] REQUEST FAILED | id={request_id} | duration={duration:.0f}ms | error={e}")
        logger.info("[API] " + "="*60)
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

@app.get("/")
async def serve_test_client():
    """Serve the test client HTML page."""
    index_file = TEST_CLIENT_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Journalyst AI Assistant API running", "docs": "/docs", "health": "/health"}
