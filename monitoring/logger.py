import logging
import sys
from pythonjsonlogger import jsonlogger
from config.settings import settings


def setup_logging():
    """
    Setup structured JSON logging for the application.
    Logs are written to stdout in JSON format for easy ingestion by log aggregators.
    """
    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Create JSON formatter
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Set levels for noisy libraries
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('kafka').setLevel(logging.WARNING)
    
    logger.info("Logging configured", extra={
        'log_level': settings.log_level,
        'format': 'json'
    })


class StructuredLogger:
    """
    Wrapper for structured logging with context.
    Adds consistent fields to all log messages.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def add_context(self, **kwargs):
        """Add persistent context to all subsequent logs"""
        self.context.update(kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method that adds context"""
        extra = {**self.context, **kwargs}
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)
