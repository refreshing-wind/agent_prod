"""Logging configuration with request and task ID tracking."""
import logging
import sys
from typing import Optional

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ContextFilter(logging.Filter):
    """Filter to inject default request_id and task_id if missing."""
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = '-'
        if not hasattr(record, 'task_id'):
            record.task_id = '-'
        return True


def setup_logging(level: str = "INFO") -> None:
    """
    Setup application logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(ContextFilter())
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[handler],
        force=True  # Force reconfiguration
    )


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter with request_id and task_id context."""
    
    def process(self, msg, kwargs):
        """Add request_id and task_id to log record."""
        request_id = self.extra.get('request_id', '-')
        task_id = self.extra.get('task_id', '-')
        return f'[{request_id}] [{task_id}] {msg}', kwargs


def get_logger(name: str, request_id: Optional[str] = None, task_id: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with optional request_id and task_id context.
    
    Args:
        name: Logger name
        request_id: Optional request ID for tracking
        task_id: Optional task ID for tracking
        
    Returns:
        Logger instance with context
    """
    logger = logging.getLogger(name)
    if request_id or task_id:
        return LoggerAdapter(logger, {'request_id': request_id or '-', 'task_id': task_id or '-'})
    return logger
