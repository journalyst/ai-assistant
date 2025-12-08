import pytest
from src.database.validator import validate_sql_query, SQLValidationError
from src.database.queries import TradeQueries

def test_sql_validator_blocks_mutations():
    """Ensure validator catches dangerous queries."""
    with pytest.raises(SQLValidationError):
        validate_sql_query("DELETE FROM trade WHERE user_id = 1")
    
    with pytest.raises(SQLValidationError):
        validate_sql_query("UPDATE trade SET pnl = 0")
    
    # Should pass
    validate_sql_query("SELECT * FROM trade WHERE user_id = 1")

def test_trades_query():
    """Test fetching trades (requires seeded DB)."""
    trades = TradeQueries.get_trades_by_user(user_id=1, limit=10)
    assert len(trades) > 0
    assert all('symbol' in t for t in trades)  # Join worked
    print(f"✓ Fetched {len(trades)} trades")

def test_performance_summary():
    """Test aggregate query."""
    summary = TradeQueries.get_performance_summary(user_id=1)
    assert 'total_trades' in summary
    assert summary['total_trades'] > 0
    print(f"✓ Win rate: {summary['wins']}/{summary['total_trades']}")