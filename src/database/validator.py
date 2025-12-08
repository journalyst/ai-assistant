import re
from typing import List
from src.logger import get_logger

logger = get_logger(__name__)

FORBIDDEN_KEYWORDS = [
    'UPDATE', 'DELETE', 'INSERT', 'DROP', 'ALTER', 'TRUNCATE', 'CREATE', 'REPLACE', 'GRANT', 'REVOKE'
]

class SQLValidationError(Exception):
    """Custom exception for SQL validation errors."""
    pass

def validate_sql_query(query: str) -> bool:
    """Validate SQL query to prevent dangerous operations."""
    upper_query = query.upper().strip()

    if not (upper_query.startswith("SELECT") or upper_query.startswith("WITH")):
        logger.warning(f"SQL Validation failed: Query must start with SELECT or WITH. Query: {query[:50]}...")
        raise SQLValidationError("Only SELECT and WITH statements are allowed.")

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(r'\b' + keyword + r'\b', upper_query):
            logger.warning(f"SQL Validation failed: Forbidden keyword '{keyword}' found. Query: {query[:50]}...")
            raise SQLValidationError(f"Forbidden SQL operation detected: {keyword}")
        
    if ';' in query.rstrip(';'):
        logger.warning(f"SQL Validation failed: Multiple statements detected. Query: {query[:50]}...")
        raise SQLValidationError("Multiple statements are not allowed.")
    
    return True