import pytest
from unittest.mock import MagicMock, patch
from src.llm.response_generator import ResponseGenerator

@pytest.fixture
def mock_openai_client():
    with patch("src.llm.response_generator.openrouter_client") as mock:
        yield mock

@pytest.fixture
def generator(mock_openai_client):
    return ResponseGenerator()

def test_generate_response_success(generator, mock_openai_client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Here is your analysis."
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = generator.generate_response("My query", "Some context")
    
    assert response == "Here is your analysis."
    mock_openai_client.chat.completions.create.assert_called_once()

def test_generate_response_failure(generator, mock_openai_client):
    mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

    response = generator.generate_response("My query", "Some context")
    
    assert "I apologize" in response
