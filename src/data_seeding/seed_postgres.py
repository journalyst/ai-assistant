"""Seed PostgreSQL schema (and optionally sample rows) from seed_data.sql.

By default this script applies DDL only (tables, indexes, constraints) and skips
legacy INSERT statements so normalized JSON seeding can be the primary source.

Set ``SEED_INCLUDE_LEGACY_DATA=true`` to also apply INSERT statements from
``sample_data/seed_data.sql``.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, text
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)

# SQL file path
SQL_FILE_PATH = Path("sample_data/seed_data.sql")


def get_rw_engine():
    """Get read-write database engine for seeding."""
    logger.info(f"Connecting to PostgreSQL at {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    engine = create_engine(
        settings.postgres_rw_dsn,
        connect_args={"connect_timeout": 10}
    )
    return engine


def read_sql_file(file_path: Path) -> str:
    """Read SQL file content."""
    if not file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def _should_skip_statement(statement: str, include_legacy_data: bool) -> bool:
    """Skip INSERT statements unless explicitly enabled."""
    if include_legacy_data:
        return False
    return statement.lstrip().upper().startswith("INSERT INTO")


def execute_sql_statements(connection, sql_content: str, include_legacy_data: bool = False):
    """Execute SQL statements from the file."""
    # Split by semicolon but handle comments properly
    statements = []
    current_statement = []
    
    for line in sql_content.split('\n'):
        stripped = line.strip()
        
        # Skip empty lines and comments
        if not stripped or stripped.startswith('--'):
            continue
        
        current_statement.append(line)
        
        # Check if statement ends
        if stripped.endswith(';'):
            full_statement = '\n'.join(current_statement)
            statements.append(full_statement)
            current_statement = []
    
    # Execute each statement
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for stmt in statements:
        if _should_skip_statement(stmt, include_legacy_data):
            skipped_count += 1
            continue

        try:
            connection.execute(text(stmt))
            success_count += 1
        except Exception as e:
            error_count += 1
            logger.error(f"Error executing statement: {e}")
            logger.debug(f"Failed statement: {stmt[:100]}...")
    
    connection.commit()
    return success_count, error_count, skipped_count


def seed_database():
    """Main seeding function."""
    logger.info("=" * 50)
    logger.info("Starting PostgreSQL Database Seeding")
    logger.info("=" * 50)
    
    include_legacy_data = os.getenv("SEED_INCLUDE_LEGACY_DATA", "false").lower() == "true"
    logger.info("Legacy INSERT seeding enabled: %s", include_legacy_data)

    # Read SQL file
    try:
        sql_content = read_sql_file(SQL_FILE_PATH)
        logger.info(f"Read SQL file: {SQL_FILE_PATH}")
    except FileNotFoundError as e:
        logger.error(str(e))
        return False
    
    # Connect and execute
    engine = get_rw_engine()
    
    try:
        with engine.connect() as connection:
            
            # Execute seed statements
            logger.info("Executing seed SQL statements...")
            success, errors, skipped = execute_sql_statements(
                connection,
                sql_content,
                include_legacy_data=include_legacy_data,
            )
            
            logger.info(
                "Executed %s statements successfully, %s errors, %s skipped",
                success,
                errors,
                skipped,
            )
            
            if errors > 0:
                logger.warning("Some statements failed - check logs for details")
            
        logger.info("=" * 50)
        logger.info("PostgreSQL seeding complete!")
        logger.info("=" * 50)
        return True
        
    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        return False
    finally:
        engine.dispose()


def main():
    """Entry point."""
    success = seed_database()
    if success:
        print("\n✓ PostgreSQL database seeded successfully!")
        if os.getenv("SEED_INCLUDE_LEGACY_DATA", "false").lower() == "true":
            print("  Legacy sample rows loaded from sample_data/seed_data.sql")
        else:
            print("  Schema initialized (legacy sample rows skipped)")
    else:
        print("\n✗ PostgreSQL seeding failed - check logs for details")
        exit(1)


if __name__ == "__main__":
    main()
