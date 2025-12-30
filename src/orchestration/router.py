import time
import json
from typing import Optional
from src.config import settings
from src.logger import get_logger
from src.utils.clients import get_openai_client, get_openrouter_client
from .followup_detector import RuleBasedFollowupDetector

logger = get_logger(__name__)

SYSTEM_PROMPT = """
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

class QueryRouter:
    """
    Routes and classifies user queries to determine data sources and follow-up status.
    """
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
                        {"role": "system", "content": SYSTEM_PROMPT},
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
                        {"role": "system", "content": SYSTEM_PROMPT},
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
        """
        if not previous_query:
            return {
                "is_followup": False,
                "confidence": 1.0,
                "reasoning": "No previous query in conversation"
            }
        
        start_time = time.perf_counter()
        query_preview = current_query[:40] + "..." if len(current_query) > 40 else current_query
        
        logger.info(f"[ROUTER] Detecting follow-up | current='{query_preview}'")
        
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
