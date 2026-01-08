import time
import redis
import json
from datetime import datetime
from typing import List, Optional
from tiktoken import get_encoding

from src.config import settings
from src.logger import get_logger
from src.utils.json_encoder import PostgreSQLEncoder

logger = get_logger(__name__)
redis_client = redis.from_url(settings.redis_url)

# Constants for context management
SUMMARY_TRIGGER_MESSAGE_COUNT = 15  # Trigger summarization when messages exceed this
RECENT_MESSAGES_TO_KEEP = 8  # Keep this many recent messages after summarization
SUMMARY_TOKEN_BUDGET = 500  # Max tokens for summary

class SessionManager:
    def __init__(self):
        self.redis = redis_client
        self.encoding = get_encoding("cl100k_base")
        self.model_provider = settings.model_provider
        self.max_context_window = settings.analysis_llm_context_window

    def message_token_count(self, content: str) -> int:
        """Estimate total token count for a list of messages."""
        return len(self.encoding.encode(content))
        
    def total_token_count(self, messages: List[dict]) -> int:
        """Calculate total token count for messages."""
        return sum(msg.get("token_count", 0) for msg in messages)
    
    def trim_messages_to_fit_context(self, messages: List[dict], max_tokens: int) -> List[dict]:
        """Trim messages to fit within the model's context window."""
        total_tokens = 0
        trimmed_messages = []
        
        for msg in reversed(messages):
            msg_tokens = msg.get("token_count", 0)
            if total_tokens + msg_tokens <= max_tokens:
                trimmed_messages.insert(0, msg)
                total_tokens += msg_tokens
            else:
                logger.info(f"Trimming message to fit context window. Dropping message with {msg_tokens} tokens.")
                break
        
        return trimmed_messages

    @staticmethod
    def create_session(session_id: str, user_id: str):
        logger.info(f"[SESSION] Creating new session | session_id={session_id[:8]}... | user_id={user_id}")
        session_data = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "query_contexts": [],
            "model": settings.analysis_model,
            "total_token_count": 0,
            # Hybrid context management fields
            "conversation_summary": None,  # Rolling summary of older messages
            "summary_generated_at": None,
            "messages_summarized_count": 0
        }

        redis_client.setex(f"session:{session_id}", 86400, json.dumps(session_data, cls=PostgreSQLEncoder))  # Expires in 24 hours
        logger.info(f"[SESSION] Session created and cached in Redis (TTL=24h)")

    @staticmethod
    def get_session(session_id: str) -> Optional[dict]:
        start = time.perf_counter()
        session_raw = redis_client.get(f"session:{session_id}")
        duration = (time.perf_counter() - start) * 1000
        
        if not session_raw:
            logger.info(f"[SESSION] Cache MISS | session_id={session_id[:8]}... | lookup={duration:.2f}ms")
            return None
        
        # Handle bytes from Redis
        if isinstance(session_raw, bytes):
            parsed = json.loads(session_raw.decode('utf-8'))
        else:
            parsed = json.loads(str(session_raw))
            
        msg_count = len(parsed.get("messages", []))
        token_count = parsed.get("total_token_count", 0)
        logger.info(f"[SESSION] Cache HIT | session_id={session_id[:8]}... | messages={msg_count} | tokens={token_count} | lookup={duration:.2f}ms")
        return parsed
    
    def add_message(self, session_id: str, role: str, content: str):
        start = time.perf_counter()
        key = f"session:{session_id}"
        session_raw = redis_client.get(key)
        
        # Handle bytes or None from Redis
        if session_raw is None:
            session_data = {}
        elif isinstance(session_raw, bytes):
            session_data = json.loads(session_raw.decode('utf-8'))
        else:
            session_data = json.loads(str(session_raw))
        
        if session_data:
            msg_tokens = self.message_token_count(content)
            content_preview = content[:40] + "..." if len(content) > 40 else content
            logger.info(f"[SESSION] Adding message | session_id={session_id[:8]}... | role={role} | tokens={msg_tokens} | content='{content_preview}'")
            
            session_data["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "token_count": msg_tokens
            })
            session_data["total_token_count"] = self.total_token_count(session_data["messages"])
            
            # Check if we need to generate a rolling summary
            message_count = len(session_data["messages"])
            if message_count > SUMMARY_TRIGGER_MESSAGE_COUNT:
                logger.info(f"[SESSION] Triggering rolling summary | messages={message_count} > threshold={SUMMARY_TRIGGER_MESSAGE_COUNT}")
                session_data = self._generate_and_apply_summary(session_id, session_data)
            
            # Fallback: Hard trim if still over token limit
            max_tokens = self.max_context_window
            if session_data["total_token_count"] > max_tokens:
                old_count = len(session_data["messages"])
                logger.warning(f"[SESSION] Context overflow after summary | tokens={session_data['total_token_count']}/{max_tokens} | Trimming...")
                session_data["messages"] = self.trim_messages_to_fit_context(session_data["messages"], max_tokens)
                session_data["total_token_count"] = self.total_token_count(session_data["messages"])
                new_count = len(session_data["messages"])
                logger.info(f"[SESSION] Trimmed {old_count - new_count} messages | new_tokens={session_data['total_token_count']}")

            redis_client.setex(key, 86400, json.dumps(session_data, cls=PostgreSQLEncoder))  # Refresh expiry
            duration = (time.perf_counter() - start) * 1000
            logger.info(f"[SESSION] Message saved | total_messages={len(session_data['messages'])} | total_tokens={session_data['total_token_count']} | has_summary={session_data.get('conversation_summary') is not None} | save_time={duration:.2f}ms")
        else:
            logger.error(f"[SESSION] Failed to add message - session not found | session_id={session_id[:8]}...")
    
    def _generate_and_apply_summary(self, session_id: str, session_data: dict) -> dict:
        """
        Generate a rolling summary of older messages and keep only recent ones.
        Uses LLM to compress conversation context while preserving key information.
        """
        messages = session_data.get("messages", [])
        if len(messages) <= RECENT_MESSAGES_TO_KEEP:
            return session_data
        
        # Split messages: old ones to summarize, recent ones to keep
        messages_to_summarize = messages[:-RECENT_MESSAGES_TO_KEEP]
        recent_messages = messages[-RECENT_MESSAGES_TO_KEEP:]
        
        old_summary = session_data.get("conversation_summary", "")
        
        try:
            summary_start = time.perf_counter()
            
            # Build conversation text for summarization
            conversation_text = ""
            if old_summary:
                conversation_text += f"Previous Summary:\n{old_summary}\n\n"
            
            conversation_text += "New Messages to Incorporate:\n"
            for msg in messages_to_summarize:
                conversation_text += f"{msg['role'].upper()}: {msg['content']}\n"
            
            # Generate summary using LLM
            new_summary = self._call_summary_llm(conversation_text)
            
            if new_summary:
                # Apply summary to session
                prev_summarized = session_data.get("messages_summarized_count", 0)
                session_data["conversation_summary"] = new_summary
                session_data["summary_generated_at"] = datetime.now().isoformat()
                session_data["messages_summarized_count"] = prev_summarized + len(messages_to_summarize)
                session_data["messages"] = recent_messages
                session_data["total_token_count"] = self.total_token_count(recent_messages)
                
                summary_duration = (time.perf_counter() - summary_start) * 1000
                logger.info(f"[SESSION] Rolling summary generated | session_id={session_id[:8]}... | summarized={len(messages_to_summarize)} messages | kept={len(recent_messages)} recent | summary_tokens={self.message_token_count(new_summary)} | time={summary_duration:.0f}ms")
            else:
                logger.warning(f"[SESSION] Summary generation returned empty, keeping messages as-is")
                
        except Exception as e:
            logger.error(f"[SESSION] Summary generation failed | session_id={session_id[:8]}... | error={e}")
            # On failure, just trim messages to avoid bloat
            session_data["messages"] = recent_messages
            session_data["total_token_count"] = self.total_token_count(recent_messages)
        
        return session_data
    
    def _call_summary_llm(self, conversation_text: str) -> Optional[str]:
        """
        Call LLM to generate a concise summary of conversation context.
        Uses a lightweight prompt to keep costs low.
        """
        try:
            from src.utils.clients import get_openrouter_client, get_openai_client
            
            summary_prompt = f"""Summarize this trading assistant conversation concisely (2-4 sentences).
Focus on: key trading topics discussed, specific trades/symbols mentioned, decisions or insights shared, and any ongoing analysis context.
Keep it factual and useful for continuing the conversation.

{conversation_text}

Summary:"""
            
            if settings.model_provider == "openrouter":
                client = get_openrouter_client()
                response = client.chat.completions.create(
                    model=settings.router_model or settings.analysis_model,  # Use router model if available (cheaper)
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.3,  # More deterministic
                    max_tokens=SUMMARY_TOKEN_BUDGET
                )
                content = response.choices[0].message.content
                return content.strip() if content else None
            else:
                client = get_openai_client()
                response = client.chat.completions.create(
                    model="gpt-4.1-nano-2025-04-14",  # Use cheaper model for summarization
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.3,
                    max_tokens=SUMMARY_TOKEN_BUDGET
                )
                content = response.choices[0].message.content
                return content.strip() if content else None
                
        except Exception as e:
            logger.error(f"[SESSION] LLM summary call failed | error={e}")
            return None
    
    def add_query_context(self, session_id: str, user_message: str, retrieved_data: dict, is_followup: bool = False, followup_ref: Optional[dict] = None, date_range: Optional[tuple] = None):
        """Store only identifiers and minimal metadata for a query to support follow-ups."""
        start = time.perf_counter()
        key = f"session:{session_id}"
        session_raw = redis_client.get(key)
        
        if session_raw is None:
            logger.warning(f"[SESSION] Cannot add query context - session not found | session_id={session_id[:8]}...")
            return
        
        if isinstance(session_raw, bytes):
            session_data = json.loads(session_raw.decode('utf-8'))
        else:
            session_data = json.loads(str(session_raw))
        
        if "query_contexts" not in session_data:
            session_data["query_contexts"] = []

        logger.info(f"[SESSION] Adding query context | session_id={session_id[:8]}... | is_followup={is_followup}")
        
        query_index = len(session_data.get("query_contexts", []))
        
        # Extract IDs only (no raw data)
        trade_ids = [t.get("trade_id") for t in retrieved_data.get("trades", []) if t.get("trade_id")]
        journal_ids = [j.get("id") for j in retrieved_data.get("journals", []) if j.get("id")]
        
        # Enforce ID limits to prevent session bloat
        max_trade_ids = 500
        max_journal_ids = 200
        truncated = False
        original_trade_count = len(trade_ids)
        original_journal_count = len(journal_ids)
        
        if len(trade_ids) > max_trade_ids:
            trade_ids = trade_ids[:max_trade_ids]
            truncated = True
            logger.warning(f"[SESSION] Truncated trade_ids from {original_trade_count} to {max_trade_ids}")
        
        if len(journal_ids) > max_journal_ids:
            journal_ids = journal_ids[:max_journal_ids]
            truncated = True
            logger.warning(f"[SESSION] Truncated journal_ids from {original_journal_count} to {max_journal_ids}")
        
        query_context = {
            "query_index": query_index,
            "user_message": user_message,
            "is_followup": is_followup,
            "followup_ref": followup_ref,
            "trade_ids": trade_ids,
            "trade_count": len(trade_ids),
            "journal_ids": journal_ids,
            "journal_count": len(journal_ids),
            "timestamp": datetime.now().isoformat(),
            "truncated": truncated,
            "original_trade_count": original_trade_count if truncated else len(trade_ids),
            "original_journal_count": original_journal_count if truncated else len(journal_ids)
        }
        
        # Store minimal date_range metadata if provided
        if date_range:
            query_context["date_range"] = {
                "start": date_range[0].isoformat() if date_range[0] else None,
                "end": date_range[1].isoformat() if date_range[1] else None
            }
        
        session_data["query_contexts"].append(query_context)
        redis_client.setex(key, 86400, json.dumps(session_data, cls=PostgreSQLEncoder))
        
        duration = (time.perf_counter() - start) * 1000
        trade_preview = f"{trade_ids[:5]}..." if len(trade_ids) > 5 else str(trade_ids)
        journal_preview = f"{journal_ids[:5]}..." if len(journal_ids) > 5 else str(journal_ids)
        logger.info(f"[SESSION] Query context stored | query_index={query_index} | is_followup={is_followup} | trades={len(trade_ids)} {trade_preview} | journals={len(journal_ids)} {journal_preview} | truncated={truncated} | time={duration:.2f}ms")
    
    @staticmethod
    def get_query_scope(session_id: str, query_index: int) -> Optional[dict]:
        """Retrieve the scope (trade_ids, journal_ids, etc.) for a specific query to constrain follow-ups."""
        session_raw = redis_client.get(f"session:{session_id}")
        
        if not session_raw:
            return None
        
        if isinstance(session_raw, bytes):
            session_data = json.loads(session_raw.decode('utf-8'))
        else:
            session_data = json.loads(str(session_raw))
        
        query_contexts = session_data.get("query_contexts", [])
        for ctx in query_contexts:
            if ctx.get("query_index") == query_index:
                # Backward compatibility: migrate legacy contexts with full data
                trade_ids = ctx.get("trade_ids")
                journal_ids = ctx.get("journal_ids")
                
                # Extract IDs from legacy trade_entries/journal_entries if needed
                if trade_ids is None and "trade_entries" in ctx:
                    trade_ids = [t.get("trade_id") for t in ctx.get("trade_entries", []) if t.get("trade_id")]
                    logger.warning(f"[SESSION] Legacy context detected (query_index={query_index}) - extracted {len(trade_ids)} trade_ids from trade_entries")
                
                if journal_ids is None and "journal_entries" in ctx:
                    journal_ids = [j.get("id") for j in ctx.get("journal_entries", []) if j.get("id")]
                    logger.warning(f"[SESSION] Legacy context detected (query_index={query_index}) - extracted {len(journal_ids)} journal_ids from journal_entries")
                
                scope = {
                    "trade_ids": trade_ids or [],
                    "trade_count": ctx.get("trade_count", len(trade_ids or [])),
                    "journal_ids": journal_ids or [],
                    "journal_count": ctx.get("journal_count", len(journal_ids or [])),
                    "truncated": ctx.get("truncated", False),
                    "original_trade_count": ctx.get("original_trade_count"),
                    "original_journal_count": ctx.get("original_journal_count")
                }
                
                # Include date_range if available
                if "date_range" in ctx:
                    scope["date_range"] = ctx["date_range"]
                
                return scope
        
        return None
