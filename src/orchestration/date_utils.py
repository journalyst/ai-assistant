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
    
    # Month name mappings
    MONTH_NAMES = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    @staticmethod
    def get_week_of_month(year: int, month: int, week_num: int) -> Tuple[datetime, datetime]:
        """
        Get the date range for a specific week number within a month.
        Week 1 starts on the first Monday of the month (or day 1 if it's not Monday).
        """
        # Get the first day of the month
        first_day = datetime(year, month, 1)
        
        # Find the first Monday (or use day 1 if the month starts after Monday)
        days_to_monday = (7 - first_day.weekday()) % 7
        if days_to_monday == 0 and first_day.weekday() != 0:
            first_monday = first_day
        elif first_day.weekday() <= 0:  # Monday or earlier in week
            first_monday = first_day
        else:
            first_monday = first_day + timedelta(days=days_to_monday)
        
        # Calculate the start of the requested week
        week_start = first_monday + timedelta(weeks=week_num - 1)
        week_end = week_start + timedelta(days=6)  # Full week (Mon-Sun)
        
        # Ensure we don't go past the month
        last_day_of_month = (datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)) - timedelta(days=1)
        if week_end > last_day_of_month:
            week_end = last_day_of_month
        
        return week_start, week_end
    
    @staticmethod
    def extract_date_context(query: str, current_date: datetime) -> Optional[Tuple[datetime, datetime, str]]:
        """
        Extract date range from query if mentioned.
        """
        query_lower = query.lower()
        import re
        
        # Check for specific week of month patterns (e.g., "3rd week of January", "second week of Feb")
        week_of_month_pattern = r'(\d+(?:st|nd|rd|th)?|first|second|third|fourth|last)\s+week\s+(?:of\s+)?(\w+)'
        week_match = re.search(week_of_month_pattern, query_lower)
        if week_match:
            week_str = week_match.group(1)
            month_str = week_match.group(2)
            
            # Convert word numbers to digits
            word_to_num = {
                'first': 1, '1st': 1,
                'second': 2, '2nd': 2,
                'third': 3, '3rd': 3,
                'fourth': 4, '4th': 4,
                'last': 4  # Assume last = 4th week
            }
            
            # Extract week number
            if week_str in word_to_num:
                week_num = word_to_num[week_str]
            else:
                # Extract digit from patterns like "3rd", "2nd"
                digit_match = re.match(r'(\d+)', week_str)
                week_num = int(digit_match.group(1)) if digit_match else None
            
            # Extract month
            month_num = DateQueryClassifier.MONTH_NAMES.get(month_str.lower())
            
            if week_num and month_num:
                # Determine the year (use current year or previous year if month hasn't occurred yet)
                year = current_date.year
                if month_num > current_date.month:
                    year -= 1
                
                start, end = DateQueryClassifier.get_week_of_month(year, month_num, week_num)
                month_name = datetime(year, month_num, 1).strftime('%B')
                context = f"week {week_num} of {month_name} ({start.strftime('%b %d')} - {end.strftime('%b %d')})"
                logger.info(f"Detected '{week_num} week of {month_name}' pattern -> {context}")
                return start, end, context
        
        # Check for numeric weeks pattern (e.g., "past 2 weeks", "last 3 weeks")
        weeks_match = re.search(r'(past|last|previous)\s+(\d+)\s+weeks?', query_lower)
        if weeks_match:
            n_weeks = int(weeks_match.group(2))
            start, end = WorkingDayFilter.get_last_n_days(current_date, n_weeks * 7)
            context = f"past {n_weeks} weeks ({start.strftime('%b %d')} to {end.strftime('%b %d')})"
            logger.debug(f"Detected '{n_weeks} weeks' pattern -> {context}")
            return start, end, context
        
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
        days_match = re.search(r'(past|last|previous)\s+(\d+)\s+days?', query_lower)
        if days_match:
            n_days = int(days_match.group(2))
            start, end = WorkingDayFilter.get_last_n_days(current_date, n_days)
            context = f"past {n_days} days ({start.strftime('%b %d')} to {end.strftime('%b %d')})"
            logger.debug(f"Detected '{n_days} days' pattern -> {context}")
            return start, end, context
        
        logger.debug("No date pattern detected in query")
        return None
