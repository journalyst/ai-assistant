import time
import uuid
from typing import List

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src.embeddings import get_embedding_from_cache
from src.logger import get_logger
from .qdrant_client import QdrantConnector

logger = get_logger(__name__)

class JournalStore:
    COLLECTION_NAME = "journal_entries"
    connector = QdrantConnector(collection_name=COLLECTION_NAME)

    @classmethod
    def upsert_journal(cls, user_id: int, text: str, tags: List[str], created_at: str):
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
    def search_journals(cls, user_id: int, query_text: str, limit: int = 5) -> List[dict]:
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
    def get_journals_by_ids(cls, user_id: int, journal_ids: List[str], include_text: bool = False) -> List[dict]:
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
    """Manages conversation history storage in Qdrant."""
    COLLECTION_NAME = "assistant_conversations"
    connector = QdrantConnector(collection_name=COLLECTION_NAME)
    
    @classmethod
    def upsert_conversation(cls, user_id: int, conversation_id: str, messages: List[dict]):
        """Upsert conversation history into Qdrant."""
        try:
            client = cls.connector.get_qdrant_client()
            # Flatten messages into a single text blob for embedding
            conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
            embedding = get_embedding_from_cache(conversation_text)
            point = PointStruct(
                id=conversation_id,
                vector=embedding,
                payload={
                    "user_id": user_id,
                    "messages": messages
                }
            )
            client.upsert(
                collection_name=cls.COLLECTION_NAME,
                points=[point]
            )
            logger.debug(f"Upserted conversation {conversation_id} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to upsert conversation {conversation_id} for user {user_id}: {e}")
            raise
    
    @classmethod
    def search_conversations(cls, user_id: int, query_text: str, limit: int = 3) -> List[dict]:
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
            return [
                {
                    "id": point.id,
                    "messages": point.payload.get("messages", []) # type: ignore
                }
                for point in search_result
            ]
        except Exception as e:
            logger.error(f"Failed to search conversations for user {user_id}: {e}")
            raise