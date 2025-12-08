import pytest
from unittest.mock import patch, MagicMock
from src.database.executor import QueryExecutor
from src.database.validator import SQLValidationError

@pytest.fixture
def mock_session():
    with patch("src.database.executor.get_ro_session") as mock:
        session = MagicMock()
        mock.return_value.__enter__.return_value = session
        yield session

def test_execute_raw_sql_success(mock_session):
    mock_result = MagicMock()
    mock_result.__iter__.return_value = []
    mock_session.execute.return_value = mock_result
    
    result = QueryExecutor.execute_raw_sql("SELECT * FROM trade", user_id=1, params={})
    assert isinstance(result, list)

def test_execute_raw_sql_validation_error():
    with pytest.raises(SQLValidationError):
        QueryExecutor.execute_raw_sql("DELETE FROM trade", user_id=1, params={})

def test_execute_orm_query(mock_session):
    mock_query = MagicMock()
    mock_query.all.return_value = ["result"]
    
    def query_func(session):
        return mock_query
    
    result = QueryExecutor.execute_orm_query(query_func, user_id=1)
    assert result == ["result"]
