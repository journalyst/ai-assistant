"""
Working day and week filtering utilities for trade queries.
Provides consistent date range logic across the pipeline.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional
from src.logger import get_logger

logger = get_logger(__name__)


class WorkingDayFilter:
    """Handles working day (Monday-Friday) date range calculations."""
    
    WORKING_DAYS = [0, 1, 2, 3, 4]  # Monday=0 through Friday=4
    
    @staticmethod
    def is_working_day(date: datetime) -> bool:
        """Check if date is a working day (Monday-Friday)."""
        return date.weekday() in WorkingDayFilter.WORKING_DAYS
    
    @staticmethod
    def get_last_working_week(current_date: datetime) -> Tuple[datetime, datetime]:
        """
        Get the Monday-Friday range for the last complete working week.
        
        Args:
            current_date: Reference date (typically today)
        
        Returns:
            Tuple of (monday, friday) for last week
        
        Examples:
            If today is Wednesday 2024-02-14:
                - Last week is 2024-02-05 (Mon) to 2024-02-09 (Fri)
            
            If today is Monday 2024-02-12:
                - Last week is 2024-02-05 (Mon) to 2024-02-09 (Fri)
        """
        # Find the most recent Friday (including today if it's Friday)
        days_since_friday = (current_date.weekday() - 4) % 7
        if days_since_friday == 0 and current_date.weekday() == 4:  # Today is Friday
            last_friday = current_date
        else:
            last_friday = current_date - timedelta(days=days_since_friday)
        
        # Monday is 4 days before Friday
        last_monday = last_friday - timedelta(days=4)
        
        logger.debug(f"Last working week: {last_monday.date()} to {last_friday.date()}")
        return last_monday, last_friday
    
    @staticmethod
    def get_current_working_week(current_date: datetime) -> Tuple[datetime, datetime]:
        """
        Get the Monday-to-today range for the current working week.
        
        Args:
            current_date: Reference date (typically today)
        
        Returns:
            Tuple of (monday, today)
        
        Examples:
            If today is Wednesday 2024-02-14:
                - Current week is 2024-02-12 (Mon) to 2024-02-14 (Wed)
            
            If today is Friday 2024-02-16:
                - Current week is 2024-02-12 (Mon) to 2024-02-16 (Fri)
            
            If today is Saturday 2024-02-17:
                - Current week is 2024-02-12 (Mon) to 2024-02-17 (Sat, but trade data only has Mon-Fri)
        """
        days_since_monday = current_date.weekday()
        current_monday = current_date - timedelta(days=days_since_monday)
        
        logger.debug(f"Current working week: {current_monday.date()} to {current_date.date()}")
        return current_monday, current_date
    
    @staticmethod
    def get_this_month(current_date: datetime) -> Tuple[datetime, datetime]:
        """Get first day to last day of current month."""
        first_day = current_date.replace(day=1)
        
        # Get last day of month
        if current_date.month == 12:
            last_day = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
        
        logger.debug(f"Current month: {first_day.date()} to {last_day.date()}")
        return first_day, last_day
    
    @staticmethod
    def get_this_year(current_date: datetime) -> Tuple[datetime, datetime]:
        """Get first day to last day of current year."""
        first_day = current_date.replace(month=1, day=1)
        last_day = current_date.replace(month=12, day=31)
        
        logger.debug(f"Current year: {first_day.date()} to {last_day.date()}")
        return first_day, last_day
    
    @staticmethod
    def get_last_n_days(current_date: datetime, n: int) -> Tuple[datetime, datetime]:
        """Get date range for last N days."""
        end_date = current_date
        start_date = current_date - timedelta(days=n-1)
        
        logger.debug(f"Last {n} days: {start_date.date()} to {end_date.date()}")
        return start_date, end_date
    
    @staticmethod
    def get_date_range_context(
        current_date: datetime,
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """
        Generate a natural language description of a date range for prompt context.
        
        Args:
            current_date: Today's date
            start_date: Range start
            end_date: Range end
        
        Returns:
            String description like "last working week (Feb 5 - Feb 9)"
        """
        duration_days = (end_date - start_date).days
        
        # Check if it matches common patterns
        last_week_start, last_week_end = WorkingDayFilter.get_last_working_week(current_date)
        if start_date.date() == last_week_start.date() and end_date.date() == last_week_end.date():
            return f"last working week ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"
        
        current_week_start, current_week_end = WorkingDayFilter.get_current_working_week(current_date)
        if start_date.date() == current_week_start.date() and end_date.date() == current_week_end.date():
            return f"current working week ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"
        
        if duration_days == 29 or duration_days == 30 or duration_days == 31:
            month_start, month_end = WorkingDayFilter.get_this_month(current_date)
            if start_date.date() == month_start.date() and end_date.date() == month_end.date():
                return f"this month ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"
        
        # Default: describe as date range
        return f"{start_date.strftime('%b %d')} to {end_date.strftime('%b %d')}"


class DateQueryClassifier:
    """Classifies user queries for date-related keywords and extracts date ranges."""
    
    # Patterns for different date references
    LAST_WEEK_PATTERNS = ['last week', 'previous week', 'past week', 'week ago']
    THIS_WEEK_PATTERNS = ['this week', 'current week', 'week so far']
    THIS_MONTH_PATTERNS = ['this month', 'current month', 'month so far', 'past month']
    LAST_MONTH_PATTERNS = ['last month', 'previous month']
    THIS_YEAR_PATTERNS = ['this year', 'current year', 'year to date', 'ytd']
    TODAY_PATTERNS = ['today', 'past 24 hours', 'last 24 hours']
    
    @staticmethod
    def extract_date_context(query: str, current_date: datetime) -> Optional[Tuple[datetime, datetime, str]]:
        """
        Extract date range from query if mentioned.
        
        Args:
            query: User query string
            current_date: Today's date
        
        Returns:
            Tuple of (start_date, end_date, context_description) or None if no date pattern found
        """
        query_lower = query.lower()
        
        # Check patterns in order (most specific first)
        if any(p in query_lower for p in DateQueryClassifier.LAST_WEEK_PATTERNS):
            start, end = WorkingDayFilter.get_last_working_week(current_date)
            context = WorkingDayFilter.get_date_range_context(current_date, start, end)
            logger.debug(f"Detected 'last week' pattern -> {context}")
            return start, end, context
        
        if any(p in query_lower for p in DateQueryClassifier.THIS_WEEK_PATTERNS):
            start, end = WorkingDayFilter.get_current_working_week(current_date)
            context = WorkingDayFilter.get_date_range_context(current_date, start, end)
            logger.debug(f"Detected 'this week' pattern -> {context}")
            return start, end, context
        
        if any(p in query_lower for p in DateQueryClassifier.THIS_MONTH_PATTERNS):
            start, end = WorkingDayFilter.get_this_month(current_date)
            context = WorkingDayFilter.get_date_range_context(current_date, start, end)
            logger.debug(f"Detected 'this month' pattern -> {context}")
            return start, end, context
        
        if any(p in query_lower for p in DateQueryClassifier.LAST_MONTH_PATTERNS):
            current_start, _ = WorkingDayFilter.get_this_month(current_date)
            last_month_end = current_start - timedelta(days=1)
            
            if last_month_end.month == 1:
                last_month_start = last_month_end.replace(year=last_month_end.year - 1, month=12, day=1)
            else:
                last_month_start = last_month_end.replace(month=last_month_end.month, day=1)
            
            context = WorkingDayFilter.get_date_range_context(current_date, last_month_start, last_month_end)
            logger.debug(f"Detected 'last month' pattern -> {context}")
            return last_month_start, last_month_end, context
        
        if any(p in query_lower for p in DateQueryClassifier.THIS_YEAR_PATTERNS):
            start, end = WorkingDayFilter.get_this_year(current_date)
            context = WorkingDayFilter.get_date_range_context(current_date, start, end)
            logger.debug(f"Detected 'this year' pattern -> {context}")
            return start, end, context
        
        if any(p in query_lower for p in DateQueryClassifier.TODAY_PATTERNS):
            start, end = current_date, current_date
            context = f"today ({current_date.strftime('%b %d')})"
            logger.debug(f"Detected 'today' pattern -> {context}")
            return start, end, context
        
        # Check for numeric patterns like "past 7 days", "last 30 days"
        import re
        days_match = re.search(r'(past|last|previous)\s+(\d+)\s+days?', query_lower)
        if days_match:
            n_days = int(days_match.group(2))
            start, end = WorkingDayFilter.get_last_n_days(current_date, n_days)
            context = f"past {n_days} days ({start.strftime('%b %d')} to {end.strftime('%b %d')})"
            logger.debug(f"Detected '{n_days} days' pattern -> {context}")
            return start, end, context
        
        logger.debug("No date pattern detected in query")
        return None
