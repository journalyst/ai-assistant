import pytest
from unittest.mock import patch, MagicMock
from src.vector_db.journal_store import JournalStore

@pytest.fixture
def mock_qdrant_connector():
    with patch("src.vector_db.journal_store.connector") as mock:
        yield mock

@pytest.fixture
def mock_embedding():
    with patch("src.vector_db.journal_store.get_embedding_from_cache") as mock:
        mock.return_value = [0.1, 0.2, 0.3]
        yield mock

def test_upsert_journal(mock_qdrant_connector, mock_embedding):
    client = MagicMock()
    mock_qdrant_connector.get_qdrant_client.return_value = client
    
    JournalStore.upsert_journal(1, "My journal entry", ["tag1"], "2023-01-01")
    
    client.upsert.assert_called_once()
    mock_embedding.assert_called_with("My journal entry")

def test_search_journals(mock_qdrant_connector, mock_embedding):
    client = MagicMock()
    mock_qdrant_connector.get_qdrant_client.return_value = client
    
    mock_point = MagicMock()
    mock_point.id = "uuid"
    mock_point.score = 0.9
    mock_point.payload = {"text": "Found entry", "tags": [], "created_at": "2023-01-01"}
    
    client.query_points.return_value.points = [mock_point]
    
    results = JournalStore.search_journals(1, "Search query")
    
    assert len(results) == 1
    assert results[0]["text"] == "Found entry"
    client.query_points.assert_called_once()
