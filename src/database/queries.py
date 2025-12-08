from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from .models import Trade, Assets, Strategy, Tag
from .executor import QueryExecutor
from src.logger import get_logger

logger = get_logger(__name__)

class TradeQueries:
    """Common trade-related query patterns."""
    
    @staticmethod
    def get_trades_by_user(user_id: int, limit: int = 100) -> List[Dict]:
        """Get recent trades for a user."""
        logger.debug(f"Fetching recent trades for user {user_id} (limit={limit})")
        query = """
            SELECT t.*, a.symbol, a.name as asset_name, s.name as strategy_name
            FROM trades t
            LEFT JOIN assets a ON t.asset_id = a.asset_id
            LEFT JOIN strategies s ON t.strategy_id = s.strategy_id
            WHERE t.user_id = :user_id
            ORDER BY t.trade_date DESC
            LIMIT :limit
        """
        return QueryExecutor.execute_raw_sql(query, user_id, {"user_id": user_id, "limit": limit})
    
    @staticmethod
    def get_trades_by_date_range(user_id: int, start: datetime, end: datetime) -> List[Dict]:
        """Get trades within a date range."""
        logger.debug(f"Fetching trades for user {user_id} between {start} and {end}")
        query = """
            SELECT t.*, a.symbol, s.name as strategy_name
            FROM trades t
            LEFT JOIN assets a ON t.asset_id = a.asset_id
            LEFT JOIN strategies s ON t.strategy_id = s.strategy_id
            WHERE t.user_id = :user_id
              AND t.trade_date >= :start
              AND t.trade_date < :end
            ORDER BY t.trade_date
        """
        return QueryExecutor.execute_raw_sql(
            query, user_id, 
            {"user_id": user_id, "start": start, "end": end}
        )
    
    @staticmethod
    def get_performance_summary(user_id: int) -> Dict:
        """Calculate aggregate performance metrics."""
        logger.debug(f"Calculating performance summary for user {user_id}")
        query = """
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN pnl > 0 THEN 1 END) as wins,
                COUNT(CASE WHEN pnl < 0 THEN 1 END) as losses,
                COUNT(CASE WHEN pnl = 0 THEN 1 END) as breakeven,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as best_trade,
                MIN(pnl) as worst_trade,
                AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss
            FROM trades
            WHERE user_id = :user_id
        """
        result = QueryExecutor.execute_raw_sql(query, user_id, {"user_id": user_id})
        return result[0] if result else {}
    
    @staticmethod
    def get_trades_by_strategy(user_id: int, strategy_name: str) -> List[Dict]:
        """Get trades filtered by strategy."""
        logger.debug(f"Fetching trades for user {user_id} with strategy {strategy_name}")
        query = """
            SELECT t.*, a.symbol, s.name as strategy_name
            FROM trades t
            LEFT JOIN assets a ON t.asset_id = a.asset_id
            LEFT JOIN strategies s ON t.strategy_id = s.strategy_id
            WHERE t.user_id = :user_id
              AND LOWER(s.name) = LOWER(:strategy_name)
            ORDER BY t.trade_date DESC
        """
        return QueryExecutor.execute_raw_sql(
            query, user_id,
            {"user_id": user_id, "strategy_name": strategy_name}
        )
    
    @staticmethod
    def get_trades_by_asset(user_id: int, symbol: str) -> List[Dict]:
        """Get trades for a specific asset."""
        logger.debug(f"Fetching trades for user {user_id} on {symbol}")
        query = """
            SELECT t.*, a.symbol, s.name as strategy_name
            FROM trades t
            LEFT JOIN assets a ON t.asset_id = a.asset_id
            LEFT JOIN strategies s ON t.strategy_id = s.strategy_id
            WHERE t.user_id = :user_id
              AND UPPER(a.symbol) = UPPER(:symbol)
            ORDER BY t.trade_date DESC
        """
        return QueryExecutor.execute_raw_sql(
            query, user_id,
            {"user_id": user_id, "symbol": symbol}
        )
    
    @staticmethod
    def get_trades_by_session(user_id: int, session: str) -> List[Dict]:
        """Get trades filtered by trading session."""
        logger.debug(f"Fetching trades for user {user_id} in {session} session")
        query = """
            SELECT t.*, a.symbol, s.name as strategy_name
            FROM trades t
            LEFT JOIN assets a ON t.asset_id = a.asset_id
            LEFT JOIN strategies s ON t.strategy_id = s.strategy_id
            WHERE t.user_id = :user_id
              AND LOWER(t.session) = LOWER(:session)
            ORDER BY t.trade_date DESC
        """
        return QueryExecutor.execute_raw_sql(
            query, user_id,
            {"user_id": user_id, "session": session}
        )
    
    @staticmethod
    def get_win_rate_by_strategy(user_id: int) -> List[Dict]:
        """Calculate win rate grouped by strategy."""
        logger.debug(f"Calculating win rate by strategy for user {user_id}")
        query = """
            SELECT 
                s.name as strategy_name,
                COUNT(*) as total_trades,
                COUNT(CASE WHEN t.pnl > 0 THEN 1 END) as wins,
                ROUND(100.0 * COUNT(CASE WHEN t.pnl > 0 THEN 1 END) / COUNT(*), 2) as win_rate,
                SUM(t.pnl) as total_pnl
            FROM trades t
            LEFT JOIN strategies s ON t.strategy_id = s.strategy_id
            WHERE t.user_id = :user_id
            GROUP BY s.name
            ORDER BY win_rate DESC
        """
        return QueryExecutor.execute_raw_sql(query, user_id, {"user_id": user_id})
    
    @staticmethod
    def get_emotional_patterns(user_id: int) -> List[Dict]:
        """Analyze trading outcomes by emotional state."""
        logger.debug(f"Analyzing emotional patterns for user {user_id}")
        query = """
            SELECT 
                emotional_state,
                COUNT(*) as trade_count,
                COUNT(CASE WHEN pnl > 0 THEN 1 END) as wins,
                COUNT(CASE WHEN pnl < 0 THEN 1 END) as losses,
                ROUND(100.0 * COUNT(CASE WHEN pnl > 0 THEN 1 END) / COUNT(*), 2) as win_rate,
                SUM(pnl) as total_pnl
            FROM trades
            WHERE user_id = :user_id AND emotional_state IS NOT NULL
            GROUP BY emotional_state
            ORDER BY trade_count DESC
        """
        return QueryExecutor.execute_raw_sql(query, user_id, {"user_id": user_id})