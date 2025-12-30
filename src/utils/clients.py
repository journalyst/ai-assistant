from openai import OpenAI
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)

# Global client instances (lazy initialization)
_openrouter_client = None
_openai_client = None

def get_openrouter_client() -> OpenAI:
    """
    Get or create a shared OpenRouter client.
    Uses lazy initialization to avoid creating clients at import time.
    """
    global _openrouter_client
    if _openrouter_client is None:
        logger.debug("[CLIENTS] Initializing OpenRouter client")
        _openrouter_client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    return _openrouter_client

def get_openai_client() -> OpenAI:
    """
    Get or create a shared OpenAI client.
    Uses lazy initialization to avoid creating clients at import time.
    """
    global _openai_client
    if _openai_client is None:
        logger.debug("[CLIENTS] Initializing OpenAI client")
        _openai_client = OpenAI(
            api_key=settings.openai_api_key
        )
    return _openai_client

def get_llm_client():
    """
    Get the appropriate LLM client based on the configured provider.
    Returns tuple of (provider_name, client).
    """
    if settings.model_provider == "openrouter":
        return "openrouter", get_openrouter_client()
    else:
        return "openai", get_openai_client()
