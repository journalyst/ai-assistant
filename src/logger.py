import logging
import sys
import os
from src.config import settings

# Custom formatter with colors for console output
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels and component tags."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',
    }
    
    # Component colors for easier visual parsing
    COMPONENT_COLORS = {
        '[API]': '\033[94m',         # Light blue
        '[ROUTER]': '\033[95m',      # Light magenta
        '[RETRIEVER]': '\033[96m',   # Light cyan
        '[SQL]': '\033[93m',         # Light yellow
        '[VECTOR_SEARCH]': '\033[92m', # Light green
        '[CACHE': '\033[91m',        # Light red (for HIT/MISS visibility)
        '[SESSION]': '\033[97m',     # White
        '[LLM]': '\033[35m',         # Magenta
        '[LLM_STREAM]': '\033[35m',  # Magenta
    }
    
    def format(self, record):
        # Apply level color
        level_color = self.COLORS.get(record.levelname, '')
        reset = self.COLORS['RESET']
        
        # Format the message first
        formatted = super().format(record)
        
        # Apply component colors to the message
        for component, color in self.COMPONENT_COLORS.items():
            if component in formatted:
                formatted = formatted.replace(component, f'{color}{component}{reset}')
        
        # Highlight CACHE HIT/MISS
        if '[CACHE HIT]' in formatted:
            formatted = formatted.replace('[CACHE HIT]', f'\033[42m[CACHE HIT]\033[0m')  # Green background
        elif '[CACHE MISS]' in formatted:
            formatted = formatted.replace('[CACHE MISS]', f'\033[43m[CACHE MISS]\033[0m')  # Yellow background
        
        # Highlight session cache hits/misses
        if 'Cache HIT' in formatted:
            formatted = formatted.replace('Cache HIT', f'\033[42mCache HIT\033[0m')
        elif 'Cache MISS' in formatted:
            formatted = formatted.replace('Cache MISS', f'\033[43mCache MISS\033[0m')
        
        # Color the log level
        formatted = formatted.replace(
            f'[{record.levelname}]',
            f'{level_color}[{record.levelname}]{reset}'
        )
        
        return formatted


def setup_logging():
    """
    Configures the logging system with both file and console output.
    Console output has colors, file output is plain text.
    """
    log_format = "[%(asctime)s] [%(levelname)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Ensure log directory exists
    log_dir = os.path.dirname(settings.log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # File handler (plain text)
    file_handler = logging.FileHandler(settings.log_file)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(file_handler)
    
    # Console handler (with colors)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler)

    # Set lower level for some noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance with the given name.
    """
    return logging.getLogger(name)

# Initialize logging on import
setup_logging()
