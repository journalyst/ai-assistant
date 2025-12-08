from .qdrant_client import QdrantConnector
from src.embeddings import get_embedding_from_cache
from src.logger import get_logger
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from typing import List
import uuid

logger = get_logger(__name__)
connector = QdrantConnector()

class JournalStore:
    COLLECTION_NAME = "journal_entries"

    @classmethod
    def upsert_journal(cls, user_id: int, text: str, tags: List[str], created_at: str):
        """Upsert a journal entry into Qdrant."""
        try:
            client = connector.get_qdrant_client()
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
        import time
        total_start = time.perf_counter()
        query_preview = query_text[:50] + "..." if len(query_text) > 50 else query_text
        
        logger.info(f"[VECTOR_SEARCH] Starting journal search | user_id={user_id} | limit={limit} | query='{query_preview}'")
        
        try:
            client = connector.get_qdrant_client()
            
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