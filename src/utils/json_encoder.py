import json
from datetime import date, datetime
from decimal import Decimal


class PostgreSQLEncoder(json.JSONEncoder):
    """
    JSON encoder to handle PostgreSQL/Python types.
    
    Handles:
    - Decimal -> float
    - datetime -> ISO format string
    - date -> ISO format string
    """
    
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)
