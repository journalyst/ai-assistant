from __future__ import annotations
from typing import AsyncGenerator, Optional, TYPE_CHECKING
import asyncio
import json
import time

from src.logger import get_logger
from src.cache.session import SessionManager
from src.llm.response_generator import ResponseGenerator
from src.utils.json_encoder import PostgreSQLEncoder

if TYPE_CHECKING:
    from src.orchestration.retriever import DataRetriever
    from .schemas import ChatRequest

logger = get_logger(__name__)

def mask_dsn(dsn: str) -> str:
    """Mask password in database connection string for safe logging."""
    if ":" in dsn and "@" in dsn:
        pre, rest = dsn.split(":", 1)
        pwd_and_host = rest.split("@", 1)
        if len(pwd_and_host) == 2:
            return pre + ":***@" + pwd_and_host[1]
    return dsn

def build_compact_context(
    retrieved_data: dict,
    is_followup: bool = False,
    anchor_scope: Optional[dict] = None
) -> str:
    """
    Build a compact context summary for LLM consumption.
    """
    trade_count = len(retrieved_data.get("trades", []))
    journal_count = len(retrieved_data.get("journals", []))
    
    # Extract summary stats from trades
    trades = retrieved_data.get("trades", [])
    total_pnl = sum(t.get("pnl", 0) for t in trades) if trades else 0
    symbols = list(set(t.get("symbol", "N/A") for t in trades)) if trades else []
    
    # Build context text
    context_parts = []
    
    if is_followup and anchor_scope:
        context_parts.append("FOLLOW-UP CONTEXT (analyzing previous query scope):")
        context_parts.append(f"- Anchor trades: {len(anchor_scope.get('trade_ids', []))} IDs")
        context_parts.append(f"- Anchor journals: {len(anchor_scope.get('journal_ids', []))} IDs")
        if anchor_scope.get("date_range"):
            dr = anchor_scope["date_range"]
            context_parts.append(f"- Date range: {dr.get('start', 'N/A')} to {dr.get('end', 'N/A')}")
    else:
        context_parts.append("DATA SUMMARY:")
    
    if trade_count > 0:
        context_parts.append(f"- Trades retrieved: {trade_count}")
        context_parts.append(f"- Total P&L: ${total_pnl:.2f}")
        context_parts.append(f"- Symbols: {', '.join(symbols[:10])}{'...' if len(symbols) > 10 else ''}")
        context_parts.append(f"- Trade details: {json.dumps(trades, cls=PostgreSQLEncoder)}")
    
    if journal_count > 0:
        journals = retrieved_data.get("journals", [])
        context_parts.append(f"- Journal entries retrieved: {journal_count}")
        context_parts.append(f"- Journal details: {json.dumps(journals, cls=PostgreSQLEncoder)}")
    
    return "\n".join(context_parts)

def build_history_text(session: Optional[dict], user_id: Optional[str], query_text: Optional[str]) -> str:
    """
    Build conversation history text from session using hybrid approach:
    1. Rolling summary of older conversations (compressed context)
    2. Recent messages (last 8-10 in full)
    3. Semantically relevant past conversations from vector DB
    """
    if not session:
        return ""
    
    context_parts = []
    
    # 1. Add rolling summary if exists (compressed older context)
    conversation_summary = session.get("conversation_summary")
    if conversation_summary:
        messages_summarized = session.get("messages_summarized_count", 0)
        context_parts.append(f"[Previous Conversation Summary - {messages_summarized} messages compressed]")
        context_parts.append(conversation_summary)
        context_parts.append("")  # Empty line separator
        logger.debug(f"[CONTEXT] Added rolling summary | summarized_count={messages_summarized}")
    
    # 2. Add recent messages (full content)
    recent_messages = session.get("messages", [])
    if recent_messages:
        context_parts.append("Recent Conversation:")
        for msg in recent_messages[-10:]:  # Last 10 messages
            context_parts.append(f"{msg['role'].upper()}: {msg['content']}")
        context_parts.append("")  # Empty line separator
        logger.debug(f"[CONTEXT] Added {len(recent_messages[-10:])} recent messages")
    
    # 3. Add semantically relevant past conversations from vector DB (cross-session)
    if user_id and query_text:
        try:
            from src.vector_db.vector_store import AssistantConversationStore
            relevant_entries = AssistantConversationStore.search_conversations(
                user_id=str(user_id),
                query_text=str(query_text),
                limit=2  # Limit to avoid context bloat
            )
            if relevant_entries:
                context_parts.append("Relevant Past Conversations:")
                for entry in relevant_entries:
                    messages = entry.get("messages", [])
                    # Only include last few messages from each relevant conversation
                    for msg in messages[-4:]:
                        context_parts.append(f"{msg['role'].upper()}: {msg['content']}")
                context_parts.append("")
                logger.debug(f"[CONTEXT] Added {len(relevant_entries)} relevant past conversations from vector DB")
        except ImportError:
            logger.warning("AssistantConversationStore not available for retrieving relevant conversations.")
        except Exception as e:
            logger.error(f"Error retrieving relevant conversations: {e}")
    
    if not context_parts:
        return ""
    
    return "Conversation History:\n" + "\n".join(context_parts) + "\n"

async def generate_stream_response(
    request: "ChatRequest",
    retriever: "DataRetriever",
    retrieved_data: dict,
    start_time: float,
    request_id: str = "unknown",
    is_followup: bool = False,
    trade_scope: Optional[list] = None,
    anchor_scope: Optional[dict] = None
) -> AsyncGenerator[str, None]:
    """
    Async generator for Server-Sent Events (SSE) streaming.
    
    Yields SSE-formatted events with text chunks for real-time response streaming.
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
        yield f"event: start\ndata: {json.dumps(start_event['data'], cls=PostgreSQLEncoder)}\n\n"
        
        # Send retrieved data
        data_event = {
            "trade_data": retrieved_data.get("trade_data", []),
            "journal_data": retrieved_data.get("journal_data", [])
        }
        yield f"event: data\ndata: {json.dumps(data_event, cls=PostgreSQLEncoder)}\n\n"
        
        # Stream LLM response
        llm_start = time.perf_counter()
        generator = ResponseGenerator()
        
        # Build context with session history
        session_mgr = SessionManager()
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
        
        full_response = ""
        chunk_count = 0
        for chunk in generator.generate_response_stream(
            user_query=request.query,
            context=context_str,
            user_name=request.user_name,
            current_date=current_date,
            date_period_context=date_period_context,
            is_followup=is_followup,
            trade_scope=trade_scope
        ):
            full_response += chunk
            chunk_count += 1
            yield f"event: chunk\ndata: {json.dumps({'text': chunk}, cls=PostgreSQLEncoder)}\n\n"
            await asyncio.sleep(0.01)
        
        # Save assistant response to session
        if request.session_id:
            session_mgr.add_message(request.session_id, "assistant", full_response)
        
        # Store conversation to vector DB (with optimizations)
        if full_response:
            from src.vector_db.vector_store import AssistantConversationStore
            try:
                # Get updated session to include any generated summary
                updated_session = session_mgr.get_session(request.session_id) if request.session_id else None
                messages_to_store = (updated_session["messages"] if updated_session else [])
                conversation_summary = updated_session.get("conversation_summary") if updated_session else None
                
                AssistantConversationStore.upsert_conversation(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    messages=messages_to_store,
                    conversation_summary=conversation_summary
                )
            except Exception as e:
                logger.error(f"[API] Failed to upsert conversation to vector DB | error={e}")
                
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
        yield f"event: done\ndata: {json.dumps(done_event, cls=PostgreSQLEncoder)}\n\n"
        
        logger.info(f"[API] STREAM COMPLETE | id={request_id} | llm={llm_duration:.0f}ms | total={total_duration:.0f}ms | chunks={chunk_count}")
        logger.info("[API] " + "="*60)
        
    except Exception as e:
        duration = (time.perf_counter() - start_time) * 1000
        logger.exception(f"[API] STREAM FAILED | id={request_id} | duration={duration:.0f}ms | error={e}")
        logger.info("[API] " + "="*60)
        error_event = {"error": str(e)}
        yield f"event: error\ndata: {json.dumps(error_event, cls=PostgreSQLEncoder)}\n\n"

async def generate_out_of_domain_response(
    response_text: str,
    start_time: float,
    request_id: str = "unknown"
) -> AsyncGenerator[str, None]:
    """
    Async generator for out-of-domain query rejection (SSE streaming).
    
    Yields a polite rejection message for queries outside the trading domain.
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
        yield f"event: start\ndata: {json.dumps(start_event['data'], cls=PostgreSQLEncoder)}\n\n"
        
        # Send data event (empty for out-of-domain)
        data_event = {"trade_data": [], "journal_data": []}
        yield f"event: data\ndata: {json.dumps(data_event, cls=PostgreSQLEncoder)}\n\n"
        
        # Send response as single chunk
        yield f"event: chunk\ndata: {json.dumps({'text': response_text}, cls=PostgreSQLEncoder)}\n\n"
        
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
        yield f"event: done\ndata: {json.dumps(done_event, cls=PostgreSQLEncoder)}\n\n"
        
        logger.info(f"[API] OUT-OF-DOMAIN STREAM COMPLETE | id={request_id} | total={total_duration:.0f}ms")
        
    except Exception as e:
        duration = (time.perf_counter() - start_time) * 1000
        logger.exception(f"[API] OUT-OF-DOMAIN STREAM FAILED | id={request_id} | duration={duration:.0f}ms | error={e}")
        error_event = {"error": str(e)}
        yield f"event: error\ndata: {json.dumps(error_event, cls=PostgreSQLEncoder)}\n\n"

# Constants
OUT_OF_DOMAIN_RESPONSE = (
    "I'm specifically designed to help with trading analysis and performance insights. "
    "Your question is outside my area of expertise. Please ask me about your trades, "
    "strategies, performance metrics, or trading psychology."
)
