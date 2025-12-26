import time
import re
from openai import OpenAI
from src.config import settings
from src.logger import get_logger
import json
from typing import Optional

logger = get_logger(__name__)

# Initialize clients lazily based on provider
openrouter_client = None
openai_client = None

def get_openrouter_client():
    global openrouter_client
    if openrouter_client is None:
        openrouter_client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    return openrouter_client

def get_openai_client():
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(
            api_key=settings.openai_api_key
        )
    return openai_client


system_prompt = """
You are the Query Analyzer for Journalyst, an AI trading assistant.
Your task is to analyze user input and determine which data sources are required to answer it.

Available Data Sources:
1. SQL Database: Structured trade data (executions, P&L, symbols, strategies, timestamps, accounts).
2. Vector Database: Unstructured journal entries (daily notes, emotional reflections, tags, text logs).

Output Schema (JSON):
{
    "is_in_domain": boolean, // True if related to trading, finance, psychology, or the user's data. False if completely unrelated.
    "query_type": string, // One of: "trade_only", "journal_only", "mixed", "general_chat"
}

Classification Rules:
- "trade_only": Questions about performance metrics, specific trade details, P&L, win rates, or account balances.
  Examples: "What's my win rate this month?", "Show me my AAPL trades", "Best performing strategy?".

- "journal_only": Questions about thoughts, feelings, specific notes, or text searches within journals.
  Examples: "What did I say about patience?", "Show entries tagged 'FOMO'", "Why was I frustrated last week?".

- "mixed": Questions connecting performance/data with qualitative factors/notes.
  Examples: "P&L on days I felt anxious", "Show trades where I noted 'revenge trading'", "Do I trade better when I journal?".

- "general_chat": Greetings, definitions, or questions not requiring user data.
  Examples: "Hello", "What is a stop loss?", "Help me calculate position size" (if generic).

Constraints:
- Always return valid JSON.
- If the user asks to perform an action (update, delete), classify as "general_chat" (the system will handle the refusal).
"""

followup_detection_prompt = """
You are analyzing whether a user's message is a follow-up question to a previous query.

Determine if this message:
1. References results from the previous query ("those", "that", "those losses", "why did they happen")
2. Asks for explanation/analysis of previous results
3. Doesn't introduce a new time period or different data scope
4. Would be unclear without the context of the previous message

Output JSON:
{
    "is_followup": boolean,
    "confidence": float (0.0-1.0),
    "reasoning": string
}
"""

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
    
    @staticmethod
    def detect(current_query: str, previous_query: Optional[str] = None) -> dict:
        """
        Detect if current_query is a follow-up to previous_query using rules.
        
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
                        "reasoning": f"Contains referential pronoun with interrogative - references previous context"
                    }
        
        # Edge case 3: Check for explicit reference patterns
        reference_patterns = [
            r'\b(those|these|that|the)\s+(trade|trades|loss|losses|profit|win|gains?|result|number|figure|stat)\b',
            r'\b(my|the)\s+(previous|last|earlier)\s+',
            r'\bfrom\s+(that|the\s+previous|earlier|before)',
            r'\bin\s+(that|those|these)\b',
            r'\babout\s+(that|those|these|them|it)\b'
        ]
        
        for pattern in reference_patterns:
            if re.search(pattern, current_lower):
                return {
                    "is_followup": True,
                    "confidence": 0.90,
                    "reasoning": f"Explicit reference pattern detected: references previous query data"
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
        # Filter out stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'my', 'i', 'me', 'was', 'were', 'is', 'are'}
        meaningful_overlap = common_words - stop_words
        
        overlap_ratio = len(meaningful_overlap) / max(len(current_set - stop_words), 1)
        if overlap_ratio > 0.4:
            return {
                "is_followup": False,
                "confidence": 0.70,
                "reasoning": f"High lexical overlap ({overlap_ratio:.2f}) - likely rephrased query or related new query"
            }
        
        # Edge case 8: Check for comparative/contrasting language (usually new query)
        comparative_patterns = [
            r'\bcompare\b', r'\bvs\b', r'\bversus\b', r'\bdifference between\b',
            r'\brather than\b', r'\binstead of\b', r'\bbetter than\b', r'\bworse than\b'
        ]
        if any(re.search(pattern, current_lower) for pattern in comparative_patterns):
            return {
                "is_followup": False,
                "confidence": 0.82,
                "reasoning": "Comparative language - likely new analytical query"
            }
        
        # Edge case 9: Questions about causes/explanations without clear reference
        # "Why did X happen?" without "those", "that" etc. is ambiguous
        if re.search(r'\bwhy (did|do|does|was|were|is|are)\b', current_lower):
            if not has_referential:
                # Check if shares subject with previous query
                # Extract potential subjects (simple heuristic)
                current_subjects = re.findall(r'\b(trade|trades|loss|losses|profit|win|strategy|performance|result)\b', current_lower)
                previous_subjects = re.findall(r'\b(trade|trades|loss|losses|profit|win|strategy|performance|result)\b', previous_lower)
                
                if set(current_subjects) & set(previous_subjects):
                    return {
                        "is_followup": True,
                        "confidence": 0.75,
                        "reasoning": "Asks 'why' about same subject as previous query"
                    }
        
        # Edge case 10: Greetings or meta questions are never follow-ups
        greetings = {'hello', 'hi', 'hey', 'thanks', 'thank you', 'ok', 'okay', 'got it'}
        if current_lower in greetings:
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


class QueryRouter:
    def __init__(self):
        if settings.model_provider == "openrouter":
            self.provider = "openrouter"
            self.client = get_openrouter_client()
        else:
            self.provider = "openai"
            self.client = get_openai_client()
        self.model = settings.router_model

    def analyze_query(self, user_query: str) -> dict:
        """
        Classifies the user query into a specific category.
        """
        start_time = time.perf_counter()
        query_preview = user_query[:50] + "..." if len(user_query) > 50 else user_query
        
        logger.info(f"[ROUTER] Classifying query via {self.provider}/{self.model} | query='{query_preview}'")
        
        try:
            if self.provider == "openrouter":
                logger.info(f"[ROUTER] Sending request to OpenRouter model '{self.model}'")
                api_start = time.perf_counter()
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_query}
                    ],
                    temperature=0,
                    response_format={"type": "json_object"}
                )
                api_duration = (time.perf_counter() - api_start) * 1000
                content = response.choices[0].message.content
                
                # Log token usage if available
                usage = getattr(response, 'usage', None)
                if usage:
                    logger.debug(f"[ROUTER] Token usage: input={usage.prompt_tokens}, output={usage.completion_tokens}, total={usage.total_tokens}")
            else:
                logger.info(f"[ROUTER] Sending request to OpenAI model '{self.model}'")
                api_start = time.perf_counter()
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_query}
                    ]
                )
                api_duration = (time.perf_counter() - api_start) * 1000
                content = response.output_text
                
            if not content:
                raise ValueError("Empty response from router model")
                
            result = json.loads(content)
            total_duration = (time.perf_counter() - start_time) * 1000
            
            logger.info(f"[ROUTER] Classification complete | type='{result.get('query_type')}' | in_domain={result.get('is_in_domain')} | api_call={api_duration:.0f}ms | total={total_duration:.0f}ms")
            return result

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"[ROUTER] Classification FAILED after {duration:.2f}ms: {e}")
            # Fallback to general chat if routing fails
            return {
                "is_in_domain": True,
                "query_type": "general_chat",
                "reasoning": f"Routing failed: {str(e)}"
            }
    
    def detect_followup(self, current_query: str, previous_query: Optional[str] = None) -> dict:
        """
        Detects if the current query is a follow-up to the previous query.
        Returns metadata about whether it's a follow-up and confidence level.
        """
        if not previous_query:
            return {
                "is_followup": False,
                "confidence": 1.0,
                "reasoning": "No previous query in conversation"
            }
        
        start_time = time.perf_counter()
        query_preview = current_query[:40] + "..." if len(current_query) > 40 else current_query
        
        logger.info(f"[ROUTER] Detecting follow-up | current='{query_preview}' | provider={self.provider}/{self.model}")
        
        try:
            # Use rule-based detection
            result = RuleBasedFollowupDetector.detect(current_query, previous_query)
            
            total_duration = (time.perf_counter() - start_time) * 1000
            
            is_followup = result.get("is_followup", False)
            confidence = result.get("confidence", 0.0)
            reasoning = result.get("reasoning", "")
            logger.info(f"[ROUTER] Follow-up detection complete | is_followup={is_followup} | confidence={confidence:.2f} | reasoning={reasoning} | total={total_duration:.2f}ms")
            
            return result
        
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.exception(f"[ROUTER] Follow-up detection FAILED after {duration:.2f}ms: {e}")
            # Default to non-followup if detection fails
            return {
                "is_followup": False,
                "confidence": 0.0,
                "reasoning": f"Detection failed: {str(e)}"
            }
