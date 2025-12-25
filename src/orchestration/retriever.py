import time
from datetime import datetime
from src.database.executor import QueryExecutor
from src.database.queries import TradeQueries
from .router import QueryRouter
from .date_utils import DateQueryClassifier
from src.vector_db.journal_store import JournalStore
from src.logger import get_logger
from typing import Dict, Any, Optional, Tuple

logger = get_logger(__name__)

class DataRetriever:
    """Retrieves data from various sources based on user queries."""

    # NOTE: For testing with the 2024 seed dataset, we pin "today" to the last date in seed_data.sql (Feb 15, 2024).
    # Change this back to datetime.now() before pushing to production.
    TEST_SEED_CURRENT_DATE = datetime(2024, 2, 15)

    def __init__(self, user_id: int, current_date: Optional[datetime] = None):
        self.user_id = user_id
        # self.current_date = current_date or datetime.now()
        self.current_date = current_date or DataRetriever.TEST_SEED_CURRENT_DATE
        self.query_analysis = None
        self.date_context = None  # Store extracted date context
        self.timings = {}  # Track component timings

    def retrieve_data(self, user_query: str, anchor_scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Retrieve data based on the analyzed query type. If anchor_scope provided, constrain to those IDs."""
        total_start = time.perf_counter()
        query_preview = user_query[:60] + "..." if len(user_query) > 60 else user_query
        
        logger.info(f"[RETRIEVER] Starting data retrieval for user {self.user_id} | query='{query_preview}' | anchored={anchor_scope is not None}")
        
        # Step 0: Extract date context from query
        date_context = DateQueryClassifier.extract_date_context(user_query, self.current_date)
        self.date_context = date_context
        if date_context:
            start_date, end_date, context_desc = date_context
            logger.info(f"[RETRIEVER] Date context detected: {context_desc}")
        
        # If anchor_scope is provided (follow-up), use ID-based retrieval
        if anchor_scope and (anchor_scope.get("trade_ids") or anchor_scope.get("journal_ids")):
            return self._retrieve_anchored(user_query, anchor_scope)
        
        # Otherwise, standard router-based retrieval
        return self._retrieve_standard(user_query, date_context)
        
        # Step 1: Route the query
        router_start = time.perf_counter()
        self.query_analysis = QueryRouter().analyze_query(user_query)
        self.timings["router"] = (time.perf_counter() - router_start) * 1000
        
        data = {}
        query_type = self.query_analysis.get("query_type")
        is_in_domain = self.query_analysis.get("is_in_domain", True)
        
        logger.info(f"[RETRIEVER] Query classified as '{query_type}' (in_domain={is_in_domain}) in {self.timings['router']:.2f}ms")

        # Step 2: Retrieve trade data if needed
        if query_type in ["trade_only", "mixed"]:
            trade_start = time.perf_counter()
            logger.info(f"[RETRIEVER] Fetching trade data from PostgreSQL for user {self.user_id}...")
            
            # Use date range if extracted from query, otherwise fetch all trades
            if date_context:
                start_date, end_date, _ = date_context
                trades = TradeQueries.get_trades_by_date_range(self.user_id, start_date, end_date)
            else:
                trades = TradeQueries.get_trades_by_user(self.user_id)
            
            self.timings["trades_db"] = (time.perf_counter() - trade_start) * 1000
            data["trades"] = trades
            logger.info(f"[RETRIEVER] Retrieved {len(trades)} trades in {self.timings['trades_db']:.2f}ms")

        # Step 3: Retrieve journal data if needed
        if query_type in ["journal_only", "mixed"]:
            journal_start = time.perf_counter()
            logger.info(f"[RETRIEVER] Searching journal entries in Qdrant for user {self.user_id}...")
            journal_store = JournalStore()
            journals = journal_store.search_journals(
                user_id=self.user_id,
                query_text=user_query,
                limit=5
            )
            self.timings["journals_vector"] = (time.perf_counter() - journal_start) * 1000
            data["journals"] = journals
            logger.info(f"[RETRIEVER] Retrieved {len(journals)} journal entries in {self.timings['journals_vector']:.2f}ms")

        # Summary
        total_duration = (time.perf_counter() - total_start) * 1000
        self.timings["total"] = total_duration
        
        timing_breakdown = " | ".join([f"{k}={v:.0f}ms" for k, v in self.timings.items()])
        sources = list(data.keys())
        record_counts = {k: len(v) if isinstance(v, list) else 1 for k, v in data.items()}
        
        logger.info(f"[RETRIEVER] Completed | sources={sources} | records={record_counts} | {timing_breakdown}")
        return data
    
    def _retrieve_standard(self, user_query: str, date_context: Optional[Tuple]) -> Dict[str, Any]:
        """Standard router-based retrieval (non-anchored)."""
        total_start = time.perf_counter()
        
        # Step 1: Route the query
        router_start = time.perf_counter()
        self.query_analysis = QueryRouter().analyze_query(user_query)
        self.timings["router"] = (time.perf_counter() - router_start) * 1000
        
        data = {}
        query_type = self.query_analysis.get("query_type")
        is_in_domain = self.query_analysis.get("is_in_domain", True)
        
        logger.info(f"[RETRIEVER] Query classified as '{query_type}' (in_domain={is_in_domain}) in {self.timings['router']:.2f}ms")

        # Step 2: Retrieve trade data if needed
        if query_type in ["trade_only", "mixed"]:
            trade_start = time.perf_counter()
            logger.info(f"[RETRIEVER] Fetching trade data from PostgreSQL for user {self.user_id}...")
            
            # Use date range if extracted from query, otherwise fetch all trades
            if date_context:
                start_date, end_date, _ = date_context
                trades = TradeQueries.get_trades_by_date_range(self.user_id, start_date, end_date)
            else:
                trades = TradeQueries.get_trades_by_user(self.user_id)
            
            self.timings["trades_db"] = (time.perf_counter() - trade_start) * 1000
            data["trades"] = trades
            logger.info(f"[RETRIEVER] Retrieved {len(trades)} trades in {self.timings['trades_db']:.2f}ms")

        # Step 3: Retrieve journal data if needed
        if query_type in ["journal_only", "mixed"]:
            journal_start = time.perf_counter()
            logger.info(f"[RETRIEVER] Searching journal entries in Qdrant for user {self.user_id}...")
            journal_store = JournalStore()
            journals = journal_store.search_journals(
                user_id=self.user_id,
                query_text=user_query,
                limit=5
            )
            self.timings["journals_vector"] = (time.perf_counter() - journal_start) * 1000
            data["journals"] = journals
            logger.info(f"[RETRIEVER] Retrieved {len(journals)} journal entries in {self.timings['journals_vector']:.2f}ms")

        # Summary
        total_duration = (time.perf_counter() - total_start) * 1000
        self.timings["total"] = total_duration
        
        timing_breakdown = " | ".join([f"{k}={v:.0f}ms" for k, v in self.timings.items()])
        sources = list(data.keys())
        record_counts = {k: len(v) if isinstance(v, list) else 1 for k, v in data.items()}
        
        logger.info(f"[RETRIEVER] Completed (standard) | sources={sources} | records={record_counts} | {timing_breakdown}")
        return data
    
    def _retrieve_anchored(self, user_query: str, anchor_scope: Dict[str, Any]) -> Dict[str, Any]:
        """Anchored retrieval using IDs from previous query (follow-up mode)."""
        total_start = time.perf_counter()
        
        trade_ids = anchor_scope.get("trade_ids", [])
        journal_ids = anchor_scope.get("journal_ids", [])
        
        logger.info(f"[RETRIEVER] Anchored retrieval | trade_ids={len(trade_ids)} | journal_ids={len(journal_ids)}")
        
        # Fallback if anchor is empty
        if not trade_ids and not journal_ids:
            logger.warning(f"[RETRIEVER] Empty anchor_scope, falling back to standard retrieval")
            return self._retrieve_standard(user_query, self.date_context)
        
        data = {}
        
        # Fetch trades by IDs (anchor set)
        if trade_ids:
            trade_start = time.perf_counter()
            logger.info(f"[RETRIEVER] Fetching {len(trade_ids)} trades by ID for user {self.user_id}...")
            trades = TradeQueries.get_trades_by_ids(self.user_id, trade_ids)
            self.timings["trades_db"] = (time.perf_counter() - trade_start) * 1000
            data["trades"] = trades
            logger.info(f"[RETRIEVER] Retrieved {len(trades)} anchor trades in {self.timings['trades_db']:.2f}ms")
        
        # Optionally classify follow-up to decide if we need journals (augmentation)
        # Use router only to determine "do we need extra data?", not to widen trades
        router_start = time.perf_counter()
        self.query_analysis = QueryRouter().analyze_query(user_query)
        self.timings["router"] = (time.perf_counter() - router_start) * 1000
        query_type = self.query_analysis.get("query_type")
        
        logger.info(f"[RETRIEVER] Follow-up classified as '{query_type}' | router={self.timings['router']:.0f}ms")
        
        # Fetch journals if follow-up intent suggests it OR if anchor had journals
        if query_type in ["journal_only", "mixed"] or journal_ids:
            journal_start = time.perf_counter()
            
            if journal_ids:
                # Retrieve specific journals by ID (anchor set)
                logger.info(f"[RETRIEVER] Fetching {len(journal_ids)} journals by ID for user {self.user_id}...")
                journal_store = JournalStore()
                journals = journal_store.get_journals_by_ids(
                    user_id=self.user_id,
                    journal_ids=journal_ids,
                    include_text=True  # Include text for follow-up analysis
                )
                self.timings["journals_vector"] = (time.perf_counter() - journal_start) * 1000
                data["journals"] = journals
                logger.info(f"[RETRIEVER] Retrieved {len(journals)} anchor journals in {self.timings['journals_vector']:.2f}ms")
            elif query_type in ["journal_only", "mixed"]:
                # Augmentation: search for new journals relevant to follow-up
                logger.info(f"[RETRIEVER] Augmenting with journal search for user {self.user_id}...")
                journal_store = JournalStore()
                journals = journal_store.search_journals(
                    user_id=self.user_id,
                    query_text=user_query,
                    limit=5
                )
                self.timings["journals_vector"] = (time.perf_counter() - journal_start) * 1000
                data["journals"] = journals
                logger.info(f"[RETRIEVER] Augmented with {len(journals)} journals in {self.timings['journals_vector']:.2f}ms")
        
        # Summary
        total_duration = (time.perf_counter() - total_start) * 1000
        self.timings["total"] = total_duration
        
        timing_breakdown = " | ".join([f"{k}={v:.0f}ms" for k, v in self.timings.items()])
        sources = list(data.keys())
        record_counts = {k: len(v) if isinstance(v, list) else 1 for k, v in data.items()}
        
        logger.info(f"[RETRIEVER] Completed (anchored) | sources={sources} | records={record_counts} | {timing_breakdown}")
        return data