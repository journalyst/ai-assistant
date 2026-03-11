"""Backward-compatible JournalStore import path.

Prefer importing JournalStore from src.vector_db.vector_store.
"""

from .vector_store import JournalStore

__all__ = ["JournalStore"]