"""
Rule-based follow-up detection for Journalyst AI Assistant.
Replaces LLM-based detection with faster, deterministic pattern matching.
"""
import re
from typing import Optional

from src.logger import get_logger

logger = get_logger(__name__)


class RuleBasedFollowupDetector:
    """
    Rule-based follow-up detection to replace LLM calls.
    Handles various edge cases through pattern matching and heuristics.
    """
    
    # Pronouns and references that indicate follow-up
    REFERENTIAL_PRONOUNS = {
        'that', 'those', 'these', 'this', 'them', 'they', 'it',
        'such', 'said', 'mentioned', 'above', 'previous'
    }
    
    # Question starters that often indicate follow-up
    FOLLOWUP_QUESTION_STARTERS = {
        'why', 'how', 'what about', 'can you explain', 'tell me more',
        'what caused', 'what made', 'what led to', 'elaborate',
        'more details', 'more info', 'explain', 'clarify'
    }
    
    # Temporal indicators for new queries (not follow-ups)
    NEW_QUERY_TEMPORAL = {
        'today', 'yesterday', 'tomorrow', 'this week', 'last week',
        'next week', 'this month', 'last month', 'next month',
        'this year', 'last year', 'in 2024', 'in 2025',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
        'saturday', 'sunday', 'january', 'february', 'march',
        'april', 'may', 'june', 'july', 'august', 'september',
        'october', 'november', 'december'
    }
    
    # Phrases that indicate a completely new question
    NEW_QUERY_INDICATORS = {
        'show me', 'give me', 'what is', 'what was', 'what are',
        'what were', 'how many', 'list all', 'find', 'search',
        'compare', 'analyze', 'calculate', 'get my'
    }
    
    # Greetings and acknowledgments (never follow-ups)
    GREETINGS = {'hello', 'hi', 'hey', 'thanks', 'thank you', 'ok', 'okay', 'got it'}
    
    # Stop words to filter from lexical overlap
    STOP_WORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
        'for', 'of', 'with', 'by', 'from', 'my', 'i', 'me', 'was', 
        'were', 'is', 'are'
    }
    
    # Reference patterns for explicit references
    REFERENCE_PATTERNS = [
        r'\b(those|these|that|the)\s+(trade|trades|loss|losses|profit|win|gains?|result|number|figure|stat)\b',
        r'\b(my|the)\s+(previous|last|earlier)\s+',
        r'\bfrom\s+(that|the\s+previous|earlier|before)',
        r'\bin\s+(that|those|these)\b',
        r'\babout\s+(that|those|these|them|it)\b'
    ]
    
    # Comparative patterns (usually new queries)
    COMPARATIVE_PATTERNS = [
        r'\bcompare\b', r'\bvs\b', r'\bversus\b', r'\bdifference between\b',
        r'\brather than\b', r'\binstead of\b', r'\bbetter than\b', r'\bworse than\b'
    ]
    
    # Trading subjects for context matching
    TRADING_SUBJECTS = {'trade', 'trades', 'loss', 'losses', 'profit', 'win', 'strategy', 'performance', 'result'}

    @staticmethod
    def detect(current_query: str, previous_query: Optional[str] = None) -> dict:
        """
        Detect if current_query is a follow-up to previous_query using rules.
        
        Args:
            current_query: The current user query
            previous_query: The previous user query (if any)
            
        Returns:
            dict with keys: is_followup, confidence, reasoning
        """
        if not previous_query:
            return {
                "is_followup": False,
                "confidence": 1.0,
                "reasoning": "No previous query in conversation"
            }
        
        current_lower = current_query.lower().strip()
        previous_lower = previous_query.lower().strip()
        
        # Edge case 1: Very short queries (1-2 words) are often follow-ups
        current_words = current_lower.split()
        if len(current_words) <= 2:
            # Single word questions like "why?", "how?", "when?"
            if current_words[0] in {'why', 'how', 'when', 'where', 'what'}:
                return {
                    "is_followup": True,
                    "confidence": 0.95,
                    "reasoning": "Very short interrogative - likely seeking clarification on previous query"
                }
            # References like "and?", "also?", "more?"
            if current_words[0] in {'and', 'also', 'more', 'else', 'additionally'}:
                return {
                    "is_followup": True,
                    "confidence": 0.98,
                    "reasoning": "Continuation word - clear follow-up"
                }
        
        # Edge case 2: Check for referential pronouns (those, these, that, etc.)
        has_referential = any(word in current_lower for word in RuleBasedFollowupDetector.REFERENTIAL_PRONOUNS)
        
        if has_referential:
            # High confidence if pronoun + question word
            if any(current_lower.startswith(q) for q in ['why', 'how', 'what', 'when', 'where']):
                # Exception: "What is X" or "What are X" are usually new queries
                if re.search(r'\b(what is|what are|what\'s)\b', current_lower) and not has_referential:
                    pass  # Continue to other checks
                else:
                    return {
                        "is_followup": True,
                        "confidence": 0.92,
                        "reasoning": "Contains referential pronoun with interrogative - references previous context"
                    }
        
        # Edge case 3: Check for explicit reference patterns
        for pattern in RuleBasedFollowupDetector.REFERENCE_PATTERNS:
            if re.search(pattern, current_lower):
                return {
                    "is_followup": True,
                    "confidence": 0.90,
                    "reasoning": "Explicit reference pattern detected: references previous query data"
                }
        
        # Edge case 4: Check for follow-up question starters
        for starter in RuleBasedFollowupDetector.FOLLOWUP_QUESTION_STARTERS:
            if current_lower.startswith(starter):
                # Exception: If new temporal indicator present, likely new query
                has_new_temporal = any(temporal in current_lower for temporal in RuleBasedFollowupDetector.NEW_QUERY_TEMPORAL)
                if not has_new_temporal:
                    return {
                        "is_followup": True,
                        "confidence": 0.85,
                        "reasoning": f"Follow-up question starter '{starter}' without new time scope"
                    }
        
        # Edge case 5: Check if introduces new time period (indicates new query)
        has_new_temporal = any(temporal in current_lower for temporal in RuleBasedFollowupDetector.NEW_QUERY_TEMPORAL)
        if has_new_temporal:
            # Exception: If also has referential pronouns, could be "those trades from last week"
            if not has_referential:
                return {
                    "is_followup": False,
                    "confidence": 0.88,
                    "reasoning": "Introduces new time period - likely new query scope"
                }
        
        # Edge case 6: Check for new query indicators (show, give, list, etc.)
        starts_with_new_query = any(current_lower.startswith(indicator) for indicator in RuleBasedFollowupDetector.NEW_QUERY_INDICATORS)
        if starts_with_new_query:
            # Exception: "show me more about those trades" is still follow-up
            if has_referential:
                return {
                    "is_followup": True,
                    "confidence": 0.80,
                    "reasoning": "New query starter but references previous context"
                }
            return {
                "is_followup": False,
                "confidence": 0.85,
                "reasoning": "Starts with new query indicator without references"
            }
        
        # Edge case 7: Lexical overlap - if current query shares many words with previous
        current_set = set(current_lower.split())
        previous_set = set(previous_lower.split())
        common_words = current_set & previous_set
        meaningful_overlap = common_words - RuleBasedFollowupDetector.STOP_WORDS
        
        overlap_ratio = len(meaningful_overlap) / max(len(current_set - RuleBasedFollowupDetector.STOP_WORDS), 1)
        if overlap_ratio > 0.4:
            return {
                "is_followup": False,
                "confidence": 0.70,
                "reasoning": f"High lexical overlap ({overlap_ratio:.2f}) - likely rephrased query or related new query"
            }
        
        # Edge case 8: Check for comparative/contrasting language (usually new query)
        if any(re.search(pattern, current_lower) for pattern in RuleBasedFollowupDetector.COMPARATIVE_PATTERNS):
            return {
                "is_followup": False,
                "confidence": 0.82,
                "reasoning": "Comparative language - likely new analytical query"
            }
        
        # Edge case 9: Questions about causes/explanations without clear reference
        if re.search(r'\bwhy (did|do|does|was|were|is|are)\b', current_lower):
            if not has_referential:
                # Check if shares subject with previous query
                current_subjects = re.findall(r'\b(' + '|'.join(RuleBasedFollowupDetector.TRADING_SUBJECTS) + r')\b', current_lower)
                previous_subjects = re.findall(r'\b(' + '|'.join(RuleBasedFollowupDetector.TRADING_SUBJECTS) + r')\b', previous_lower)
                
                if set(current_subjects) & set(previous_subjects):
                    return {
                        "is_followup": True,
                        "confidence": 0.75,
                        "reasoning": "Asks 'why' about same subject as previous query"
                    }
        
        # Edge case 10: Greetings or meta questions are never follow-ups
        if current_lower in RuleBasedFollowupDetector.GREETINGS:
            return {
                "is_followup": False,
                "confidence": 1.0,
                "reasoning": "Greeting or acknowledgment - not a follow-up query"
            }
        
        # Default: Not a follow-up (conservative approach)
        return {
            "is_followup": False,
            "confidence": 0.60,
            "reasoning": "No clear follow-up indicators detected"
        }
