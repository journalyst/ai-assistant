import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.api.app import app

client = TestClient(app)

@pytest.fixture
def mock_components():
    with patch("src.api.app.DataRetriever") as MockRetriever, \
         patch("src.api.app.ResponseGenerator") as MockGenerator:
        
        # Setup Retriever Mock
        retriever_instance = MockRetriever.return_value
        retriever_instance.retrieve_data.return_value = {
            "trades": [{"id": 1, "pnl": 100}],
            "journals": []
        }
        retriever_instance.query_analysis = {"query_type": "trade_only"}
        
        # Setup Generator Mock
        generator_instance = MockGenerator.return_value
        generator_instance.generate_response.return_value = "Analysis of your trades."
        
        yield MockRetriever, MockGenerator

def test_chat_endpoint_integration(mock_components):
    MockRetriever, MockGenerator = mock_components
    
    payload = {
        "user_id": 1,
        "query": "How did I do last week?",
        "user_name": "TestUser"
    }
    
    response = client.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert data["response"] == "Analysis of your trades."
    assert "trades" in data["data"]
    assert data["metadata"]["query_type"] == "trade_only"
    assert "duration_ms" in data["metadata"]
    
    # Verify component interactions
    MockRetriever.assert_called_with(user_id=1)
    MockRetriever.return_value.retrieve_data.assert_called_with("How did I do last week?")
    
    MockGenerator.assert_called_once()
    MockGenerator.return_value.generate_response.assert_called()

def test_chat_endpoint_error_handling(mock_components):
    MockRetriever, _ = mock_components
    MockRetriever.side_effect = Exception("Database connection failed")
    
    payload = {
        "user_id": 1,
        "query": "Crash me"
    }
    
    response = client.post("/chat", json=payload)
    
    assert response.status_code == 500
    assert "Database connection failed" in response.json()["detail"]
