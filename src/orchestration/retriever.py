import time
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
    def __init__(self, user_id: int, current_date: Optional[datetime] = None):
        self.user_id = user_id
        self.current_date = current_date or datetime.now()
        self.query_analysis = None
        self.date_context = None  # Store extracted date context
        self.timings = {}  # Track component timings

    def retrieve_data(self, user_query: str) -> Dict[str, Any]:
        """Retrieve data based on the analyzed query type."""
        total_start = time.perf_counter()
        query_preview = user_query[:60] + "..." if len(user_query) > 60 else user_query
        
        logger.info(f"[RETRIEVER] Starting data retrieval for user {self.user_id} | query='{query_preview}'")
        
        # Step 0: Extract date context from query
        date_context = DateQueryClassifier.extract_date_context(user_query, self.current_date)
        self.date_context = date_context
        if date_context:
            start_date, end_date, context_desc = date_context
            logger.info(f"[RETRIEVER] Date context detected: {context_desc}")
        
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