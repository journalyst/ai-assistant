import time
import uuid
from typing import List, Optional

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src.embeddings import get_embedding_from_cache
from src.logger import get_logger
from .qdrant_client import QdrantConnector

logger = get_logger(__name__)

class JournalStore:
    COLLECTION_NAME = "journal_entries"
    connector = QdrantConnector(collection_name=COLLECTION_NAME)

    @classmethod
    def upsert_journal(cls, user_id: str, text: str, tags: List[str], created_at: str):
        """Upsert a journal entry into Qdrant."""
        try:
            client = cls.connector.get_qdrant_client()
            embedding = get_embedding_from_cache(text)
            point_id = str(uuid.uuid4())
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "user_id": user_id,
                    "text": text,
                    "tags": tags,
                    "created_at": created_at
                }
            )
            client.upsert(
                collection_name=cls.COLLECTION_NAME,
                points=[point]
            )
            logger.debug(f"Upserted journal entry for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to upsert journal entry for user {user_id}: {e}")
            raise

    @classmethod
    def search_journals(cls, user_id: str, query_text: str, limit: int = 5) -> List[dict]:
        """Search for relevant journal entries for a user based on query text."""
        total_start = time.perf_counter()
        query_preview = query_text[:50] + "..." if len(query_text) > 50 else query_text
        
        logger.info(f"[VECTOR_SEARCH] Starting journal search | user_id={user_id} | limit={limit} | query='{query_preview}'")
        
        try:
            client = cls.connector.get_qdrant_client()
            
            # Get embedding (may be cached)
            embed_start = time.perf_counter()
            query_embedding = get_embedding_from_cache(query_text)
            embed_duration = (time.perf_counter() - embed_start) * 1000
            
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )
            
            # Execute vector search
            search_start = time.perf_counter()
            search_result = client.query_points(
                collection_name=cls.COLLECTION_NAME,
                query=query_embedding,
                limit=limit,
                query_filter=filter_condition
            ).points
            search_duration = (time.perf_counter() - search_start) * 1000
            
            total_duration = (time.perf_counter() - total_start) * 1000
            
            # Log results with scores
            if search_result:
                scores = [f"{p.score:.3f}" for p in search_result[:3]]
                logger.info(f"[VECTOR_SEARCH] Found {len(search_result)} entries | top_scores=[{', '.join(scores)}] | embed={embed_duration:.0f}ms | search={search_duration:.0f}ms | total={total_duration:.0f}ms")
            else:
                logger.info(f"[VECTOR_SEARCH] No entries found | embed={embed_duration:.0f}ms | search={search_duration:.0f}ms | total={total_duration:.0f}ms")
            
            return [
                {
                    "id": point.id,
                    "score": point.score,
                    "text": point.payload.get("text", ""), # type: ignore
                    "tags": point.payload.get("tags", []), # type: ignore
                    "created_at": point.payload.get("created_at", "") # type: ignore
                }
                for point in search_result
            ]
        except Exception as e:
            duration = (time.perf_counter() - total_start) * 1000
            logger.error(f"[VECTOR_SEARCH] Failed after {duration:.2f}ms | user_id={user_id} | error={e}")
            raise
    
    @classmethod
    def get_journals_by_ids(cls, user_id: str, journal_ids: List[str], include_text: bool = False) -> List[dict]:
        """Retrieve specific journal entries by IDs (for follow-up scope anchoring)."""
        import time
        if not journal_ids:
            logger.debug(f"get_journals_by_ids called with empty journal_ids for user {user_id}")
            return []
        
        total_start = time.perf_counter()
        logger.info(f"[VECTOR_RETRIEVE] Fetching {len(journal_ids)} journals by ID | user_id={user_id} | include_text={include_text}")
        
        try:
            client = cls.connector.get_qdrant_client()
            
            # Retrieve specific points by ID
            retrieve_start = time.perf_counter()
            retrieved_points = client.retrieve(
                collection_name=cls.COLLECTION_NAME,
                ids=journal_ids,
                with_payload=True,
                with_vectors=False
            )
            retrieve_duration = (time.perf_counter() - retrieve_start) * 1000
            
            # Filter by user_id for security (Qdrant retrieve doesn't support filters)
            results = []
            for point in retrieved_points:
                if point.payload and point.payload.get("user_id") == user_id: # type: ignore
                    result = {
                        "id": point.id,
                        "tags": point.payload.get("tags", []), # type: ignore
                        "created_at": point.payload.get("created_at", "") # type: ignore
                    }
                    # Optionally include text (defaults to False for compact context)
                    if include_text:
                        result["text"] = point.payload.get("text", "") # type: ignore
                    results.append(result)
            
            total_duration = (time.perf_counter() - total_start) * 1000
            logger.info(f"[VECTOR_RETRIEVE] Retrieved {len(results)} journals | retrieve={retrieve_duration:.0f}ms | total={total_duration:.0f}ms")
            
            return results
        except Exception as e:
            duration = (time.perf_counter() - total_start) * 1000
            logger.error(f"[VECTOR_RETRIEVE] Failed after {duration:.2f}ms | user_id={user_id} | error={e}")
            raise

class AssistantConversationStore:
    """
    Manages conversation history storage in Qdrant.
    
    Optimized for hybrid context management:
    - Only stores conversations with meaningful content (>= MIN_MESSAGES_TO_STORE)
    - Compresses long conversations before storage
    - Stores summary + key exchanges for efficient retrieval
    """
    COLLECTION_NAME = "assistant_conversations"
    MIN_MESSAGES_TO_STORE = 5  # Don't store trivial conversations
    MAX_MESSAGES_TO_STORE = 20  # Limit stored messages to avoid bloat
    connector = QdrantConnector(collection_name=COLLECTION_NAME)
    
    @classmethod
    def upsert_conversation(cls, user_id: str, session_id: Optional[str], messages: List[dict], conversation_summary: Optional[str] = None):
        """
        Upsert conversation history into Qdrant with smart compression.
        """
        # Skip trivial conversations
        if len(messages) < cls.MIN_MESSAGES_TO_STORE:
            logger.debug(f"[VECTOR_UPSERT] Skipping - too few messages ({len(messages)} < {cls.MIN_MESSAGES_TO_STORE})")
            return
        
        try:
            client = cls.connector.get_qdrant_client()
            
            # Build embedding text - prioritize summary if available
            if conversation_summary:
                # Use summary + recent messages for embedding
                recent_messages = messages[-6:] if len(messages) > 6 else messages
                embedding_text = f"Summary: {conversation_summary}\n\nRecent:\n"
                embedding_text += "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
            else:
                # Truncate if too long
                messages_to_embed = messages[-cls.MAX_MESSAGES_TO_STORE:] if len(messages) > cls.MAX_MESSAGES_TO_STORE else messages
                embedding_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages_to_embed])
            
            embedding = get_embedding_from_cache(embedding_text)
            
            # Generate UUID if session_id is None
            point_id = session_id if session_id is not None else str(uuid.uuid4())
            
            # Store optimized payload
            payload = {
                "user_id": user_id,
                "message_count": len(messages),
                "stored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            
            # Store summary if available, otherwise store truncated messages
            if conversation_summary:
                payload["summary"] = conversation_summary
                payload["messages"] = messages[-8:]  # Keep last 8 messages
            else:
                payload["messages"] = messages[-cls.MAX_MESSAGES_TO_STORE:]
            
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )
            client.upsert(
                collection_name=cls.COLLECTION_NAME,
                points=[point]
            )
            logger.info(f"[VECTOR_UPSERT] Stored conversation | user={user_id} | session={session_id[:8] if session_id else 'none'}... | messages={len(messages)} | has_summary={conversation_summary is not None}")
        except Exception as e:
            logger.error(f"[VECTOR_UPSERT] Failed to upsert conversation for user {user_id} for session {session_id}: {e}")
            raise
    
    @classmethod
    def search_conversations(cls, user_id: str, query_text: str, limit: int = 3) -> List[dict]:
        """Search for relevant past conversations based on query text."""
        try:
            client = cls.connector.get_qdrant_client()
            query_embedding = get_embedding_from_cache(query_text)
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )
            search_result = client.query_points(
                collection_name=cls.COLLECTION_NAME,
                query=query_embedding,
                limit=limit,
                query_filter=filter_condition
            ).points
            
            results = []
            for point in search_result:
                result = {
                    "id": point.id,
                    "score": point.score,
                    "messages": point.payload.get("messages", [])  # type: ignore
                }
                # Include summary if available
                if point.payload.get("summary"):  # type: ignore
                    result["summary"] = point.payload.get("summary")  # type: ignore
                results.append(result)
            
            logger.info(f"[VECTOR_RETRIEVE] Retrieved {len(results)} conversations for user {user_id}")
            return results
        except Exception as e:
            logger.error(f"[VECTOR_RETRIEVE] Failed to search conversations for user {user_id}: {e}")
            raise