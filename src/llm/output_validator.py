import re
from src.logger import get_logger

logger = get_logger(__name__)

class OutputValidator:
    """
    A class to validate and sanitize outputs from language models.
    """

    FORBIDDEN_PATTERNS = [
        r"(?i)(drop\s+table|select\s+\*|delete\s+from|insert\s+into|update\s+set|--)",  # Prevent SQL injection
        r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]+",  # Password exposure
        r"(?i)(api[_-]?key|apikey|secret|token)\s*[:=]\s*['\"]?[^\s'\"]+",  # API keys/secrets
        r"(?i)(bearer|authorization)\s+[a-zA-Z0-9\-._~+/]+=*",  # Auth tokens
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email addresses
        r"\b(?:\d{1,5}[:-]){3}\d{1,5}\b",  # IP addresses (partial)
        r"(?i)(credit\s+card|cc|cvv|ssn|social\s+security)\s*[:=]\s*[^\s]+",  # Financial data
        r"(?i)(database|db)\s+(password|uri|connection)\s*[:=]\s*[^\s]+",  # Database credentials
        r"(?i)(private\s+key|private_key)\s*[:=]",  # Private keys
        r'sk-[a-zA-Z0-9]{20,}',  # OpenAI API key format
        r'sk-or-v1-[a-zA-Z0-9]{20,}',  # OpenRouter API key format
        r'postgres://.*:.*@',  # Database DSN with credentials
        r'user_id\s*[:=]\s*["\']?\d+["\']?(?!.*(?:your|you|trader))'
    ]

    @classmethod
    def sanitize_output(cls, output: str) -> str:
        """
        Sanitize the output by removing forbidden patterns.
        """
        response_lower = output.lower()
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, response_lower):
                logger.error(f"Forbidden pattern detected: {pattern}")
                output = re.sub(pattern, "[REDACTED]", output, flags=re.IGNORECASE)
        return output
        