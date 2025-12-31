from typing import List, Dict, Any
from sqlalchemy import text
from .connection import get_ro_session
from .validator import validate_sql_query, SQLValidationError
from src.logger import get_logger

logger = get_logger(__name__)

class QueryExecutor:
    """Executes validated SELECT queries against read-only DB."""
    
    @staticmethod
    def execute_raw_sql(query: str, user_id: str, params: Dict[str, Any]) -> List[Dict]:
        """
        Execute a raw SQL query with safety validation.
        
        Args:
            query: SQL string (must be SELECT)
            user_id: User ID for filtering validation
            params: Optional query parameters (use :param_name in query)
        
        Returns:
            List of dicts (rows)
        """
        import time
        start_time = time.perf_counter()
        query_preview = query[:80] + "..." if len(query) > 80 else query
        
        # Validate safety
        try:
            validate_sql_query(query)
            logger.debug(f"[SQL] Query validated for user {user_id}")
        except SQLValidationError as e:
            logger.warning(f"[SQL] Validation FAILED for user {user_id}: {e}")
            raise

        logger.info(f"[SQL] Executing query for user {user_id} | query='{query_preview}'")
        
        try:
            with get_ro_session() as session:
                exec_start = time.perf_counter()
                result = session.execute(text(query), params or {})
                # Convert to list of dicts
                rows = [dict(row._mapping) for row in result]
                exec_duration = (time.perf_counter() - exec_start) * 1000
                total_duration = (time.perf_counter() - start_time) * 1000
                
                logger.info(f"[SQL] Query complete | rows={len(rows)} | exec={exec_duration:.2f}ms | total={total_duration:.2f}ms")
                return rows
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"[SQL] Query FAILED after {duration:.2f}ms | user_id={user_id} | error={e}")
            raise
    
    @staticmethod
    def execute_orm_query(query_func, user_id: str) -> List:
        """
        Execute an ORM query (for type safety with models).
        
        Args:
            query_func: Function that takes session and returns query
            user_id: User ID for context
        
        Returns:
            List of ORM objects
        """
        logger.debug(f"Executing ORM query for user {user_id}")
        try:
            with get_ro_session() as session:
                query = query_func(session)
                results = query.all()
                logger.debug(f"ORM query returned {len(results)} results")
                return results
        except Exception as e:
            logger.error(f"Error executing ORM query for user {user_id}: {e}")
            raise