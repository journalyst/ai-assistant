from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)

_client = None

class QdrantConnector:
    def __init__(self, collection_name: str):
        global _client
        if _client is None:
            logger.info(f"Connecting to Qdrant at {settings.qdrant_url}")
            try:
                _client = QdrantClient(url=settings.qdrant_url)
                self._ensure_collection(_client, collection_name)
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
                raise
        self.client = _client

    def get_qdrant_client(self) -> QdrantClient:
        return self.client

    def _ensure_collection(self, client: QdrantClient, collection_name: str):
        if client is None:
            client = self.client
        
        try:
            collections = client.get_collections().collections
            if collection_name not in [col.name for col in collections]:
                logger.info(f"Creating Qdrant collection '{collection_name}' with dimension {settings.embedding_dimension}")
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=settings.embedding_dimension,
                        distance=Distance.COSINE
                    )
                )
            else:
                logger.debug(f"Qdrant collection '{collection_name}' already exists")
        except Exception as e:
            logger.error(f"Error checking/creating Qdrant collection: {e}")
            raise