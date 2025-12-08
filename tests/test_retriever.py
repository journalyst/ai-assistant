import pytest
from unittest.mock import MagicMock, patch
from src.orchestration.retriever import DataRetriever

@pytest.fixture
def mock_router():
    with patch("src.orchestration.retriever.QueryRouter") as mock:
        yield mock

@pytest.fixture
def mock_trade_queries():
    with patch("src.orchestration.retriever.TradeQueries") as mock:
        yield mock

@pytest.fixture
def mock_journal_store():
    with patch("src.orchestration.retriever.JournalStore") as mock:
        yield mock

def test_retrieve_data_trade_only(mock_router, mock_trade_queries, mock_journal_store):
    # Setup mocks
    mock_router_instance = mock_router.return_value
    mock_router_instance.analyze_query.return_value = {"query_type": "trade_only"}
    
    mock_trade_queries.get_trades_by_user.return_value = [{"id": 1, "symbol": "AAPL"}]
    
    retriever = DataRetriever(user_id=1)
    data = retriever.retrieve_data("Show trades")
    
    assert "trades" in data
    assert data["trades"][0]["symbol"] == "AAPL"
    assert "journals" not in data
    mock_journal_store.assert_not_called()

def test_retrieve_data_journal_only(mock_router, mock_trade_queries, mock_journal_store):
    mock_router_instance = mock_router.return_value
    mock_router_instance.analyze_query.return_value = {"query_type": "journal_only"}
    
    mock_journal_store_instance = mock_journal_store.return_value
    mock_journal_store_instance.search_journals.return_value = [{"text": "Feeling good"}]
    
    retriever = DataRetriever(user_id=1)
    data = retriever.retrieve_data("Journal search")
    
    assert "journals" in data
    assert data["journals"][0]["text"] == "Feeling good"
    assert "trades" not in data
    mock_trade_queries.get_trades_by_user.assert_not_called()

def test_retrieve_data_mixed(mock_router, mock_trade_queries, mock_journal_store):
    mock_router_instance = mock_router.return_value
    mock_router_instance.analyze_query.return_value = {"query_type": "mixed"}
    
    mock_trade_queries.get_trades_by_user.return_value = []
    mock_journal_store_instance = mock_journal_store.return_value
    mock_journal_store_instance.search_journals.return_value = []
    
    retriever = DataRetriever(user_id=1)
    data = retriever.retrieve_data("Mixed query")
    
    assert "trades" in data
    assert "journals" in data
