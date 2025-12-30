"""
Seed Qdrant vector database with journal entries from sample_journals.jsonl.

This script reads journal entries from the JSONL file and upserts them
into the Qdrant collection with embeddings.

Usage:
    python -m src.seed_journals
"""

import json
from pathlib import Path
from src.vector_db.vector_store import JournalStore
from src.logger import get_logger

logger = get_logger(__name__)

# Journal file path
JOURNALS_FILE_PATH = Path("sample_data/sample_journals.jsonl")


def seed_journals():
    """Seed journal entries to Qdrant vector database."""
    logger.info("=" * 50)
    logger.info("Starting Qdrant Journal Seeding")
    logger.info("=" * 50)
    
    if not JOURNALS_FILE_PATH.exists():
        logger.error(f"Journal file not found: {JOURNALS_FILE_PATH}")
        return False
    
    # Initialize connections
    journal_store = JournalStore()
    
    logger.info("Starting journal seeding process...")
    
    try:
        with open(JOURNALS_FILE_PATH, "r", encoding="utf-8") as f:
            count = 0
            errors = 0
            
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    journal_store.upsert_journal(
                        user_id=entry["user_id"],
                        text=entry["text"],
                        tags=entry.get("tags", []),
                        created_at=entry["created_at"]
                    )
                    count += 1
                    
                    if count % 10 == 0:
                        logger.info(f"Indexed {count} entries...")
                    else:
                        logger.debug(f"Indexed: {entry['text'][:50]}...")
                        
                except json.JSONDecodeError as e:
                    errors += 1
                    logger.error(f"JSON parse error: {e}")
                except Exception as e:
                    errors += 1
                    logger.error(f"Error upserting entry: {e}")
            
            logger.info("=" * 50)
            logger.info(f"Successfully indexed {count} journal entries")
            if errors > 0:
                logger.warning(f"Encountered {errors} errors during seeding")
            logger.info("=" * 50)
            
            return errors == 0
            
    except FileNotFoundError:
        logger.error(f"{JOURNALS_FILE_PATH} not found.")
        return False
    except Exception as e:
        logger.error(f"An error occurred during seeding: {e}")
        return False


def main():
    """Entry point."""
    success = seed_journals()
    if success:
        print("\n✓ Qdrant journal seeding completed successfully!")
        print("  Collection: journal_entries")
    else:
        print("\n✗ Qdrant seeding encountered issues - check logs for details")
        exit(1)


if __name__ == "__main__":
    main()
