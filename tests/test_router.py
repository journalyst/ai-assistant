import pytest
from unittest.mock import MagicMock, patch
from src.orchestration.router import QueryRouter

@pytest.fixture
def mock_openai_client():
    with patch("src.orchestration.router.openrouter_client") as mock:
        yield mock

@pytest.fixture
def router(mock_openai_client):
    return QueryRouter()

def test_analyze_query_trade_only(router, mock_openai_client):
    # Mock response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"is_in_domain": true, "query_type": "trade_only"}'
    mock_openai_client.chat.completions.create.return_value = mock_response

    result = router.analyze_query("Show me my AAPL trades")
    
    assert result["query_type"] == "trade_only"
    assert result["is_in_domain"] is True

def test_analyze_query_journal_only(router, mock_openai_client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"is_in_domain": true, "query_type": "journal_only"}'
    mock_openai_client.chat.completions.create.return_value = mock_response

    result = router.analyze_query("What did I say about patience?")
    
    assert result["query_type"] == "journal_only"

def test_analyze_query_out_of_domain(router, mock_openai_client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"is_in_domain": false, "query_type": "general_chat"}'
    mock_openai_client.chat.completions.create.return_value = mock_response

    result = router.analyze_query("How do I bake a cake?")
    
    assert result["is_in_domain"] is False

def test_analyze_query_failure(router, mock_openai_client):
    mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

    result = router.analyze_query("Test query")
    
    assert result["query_type"] == "general_chat"
    assert "Routing failed" in result["reasoning"]
