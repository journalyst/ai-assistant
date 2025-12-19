import redis
import json
from decimal import Decimal
from datetime import datetime, date
from src.config import settings
from src.logger import get_logger
from typing import List, Optional
from tiktoken import get_encoding

# Custom JSON encoder to handle PostgreSQL types (Decimal, datetime, date)
class PostgreSQLEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

logger = get_logger(__name__)
redis_client = redis.from_url(settings.redis_url)

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
            "total_token_count": 0
        }

        redis_client.setex(f"session:{session_id}", 86400, json.dumps(session_data, cls=PostgreSQLEncoder))  # Expires in 24 hours
        logger.info(f"[SESSION] Session created and cached in Redis (TTL=24h)")

    @staticmethod
    def get_session(session_id: str) -> Optional[dict]:
        import time
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
        import time
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
            max_tokens = self.max_context_window

            if session_data["total_token_count"] > max_tokens:
                old_count = len(session_data["messages"])
                logger.warning(f"[SESSION] Context overflow | session_id={session_id[:8]}... | tokens={session_data['total_token_count']}/{max_tokens} | Trimming...")
                session_data["messages"] = self.trim_messages_to_fit_context(session_data["messages"], max_tokens)
                session_data["total_token_count"] = self.total_token_count(session_data["messages"])
                new_count = len(session_data["messages"])
                logger.info(f"[SESSION] Trimmed {old_count - new_count} messages | new_tokens={session_data['total_token_count']}")

            redis_client.setex(key, 86400, json.dumps(session_data, cls=PostgreSQLEncoder))  # Refresh expiry
            duration = (time.perf_counter() - start) * 1000
            logger.info(f"[SESSION] Message saved | total_messages={len(session_data['messages'])} | total_tokens={session_data['total_token_count']} | save_time={duration:.2f}ms")
        else:
            logger.error(f"[SESSION] Failed to add message - session not found | session_id={session_id[:8]}...")
    
    def add_query_context(self, session_id: str, user_message: str, retrieved_data: dict, is_followup: bool = False, followup_ref: Optional[dict] = None):
        """Store retrieved data and metadata for a query to support follow-ups."""
        import time
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
        trade_entries = retrieved_data.get("trades", [])
        journal_entries = retrieved_data.get("journals", [])
        journal_count = len(retrieved_data.get("journals", []))
        
        query_context = {
            "query_index": query_index,
            "user_message": user_message,
            "is_followup": is_followup,
            "followup_ref": followup_ref,
            "trade_entries": trade_entries,
            "trade_count": len(trade_entries),
            "journal_entries": journal_entries,
            "journal_count": journal_count,
            "timestamp": datetime.now().isoformat()
        }
        
        session_data["query_contexts"].append(query_context)
        redis_client.setex(key, 86400, json.dumps(session_data, cls=PostgreSQLEncoder))
        
        duration = (time.perf_counter() - start) * 1000
        logger.info(f"[SESSION] Query context stored | query_index={query_index} | is_followup={is_followup} | trades={len(trade_entries)} | journals={journal_count} | time={duration:.2f}ms")
    
    @staticmethod
    def get_query_scope(session_id: str, query_index: int) -> Optional[dict]:
        """Retrieve the scope (trade_ids, etc.) for a specific query to constrain follow-ups."""
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
                return {
                    "trade_entries": ctx.get("trade_entries", []),
                    "trade_count": ctx.get("trade_count", 0),
                    "journal_entries": ctx.get("journal_entries", []),
                    "journal_count": ctx.get("journal_count", 0)
                }
        
        return None
