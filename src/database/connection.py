from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)

# Create a read-only engine
_ro_engine = None

def get_ro_engine():
    global _ro_engine
    if _ro_engine is None:
        # Mask password in log output
        dsn = settings.postgres_ro_dsn
        masked_dsn = dsn.split('@')[-1] if '@' in dsn else dsn
        logger.info(f"Initializing read-only database engine for {masked_dsn}")
        _ro_engine = create_engine(
            settings.postgres_ro_dsn,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 10,
                "options": "-c statement_timeout=5000",  # 5 seconds
            }
        )
    return _ro_engine

# Session factory
ReadOnlySession = sessionmaker(bind=get_ro_engine(), autoflush=False, autocommit=False)

@contextmanager
def get_ro_session() -> Generator[Session, None, None]:
    """Context manager for read-only DB session."""
    session = ReadOnlySession()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        raise
    finally:
        session.close()