# -*- coding: utf-8 -*-
"""
Logging Configuration Module
Provides centralized logging configuration for all SillyMD modules
"""
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


# Log directory
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Detailed format for file logs
DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'


def setup_logging(
    module_name: str,
    log_level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Setup logging for a module

    Args:
        module_name: Name of the module
        log_level: Logging level (default: INFO)
        log_to_file: Whether to log to file (default: True)
        log_to_console: Whether to log to console (default: True)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(module_name)
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    detailed_formatter = logging.Formatter(DETAILED_FORMAT, datefmt=DATE_FORMAT)

    # Add file handler
    if log_to_file:
        log_file = LOG_DIR / f"{module_name}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    # Add console handler
    if log_to_console:
        import sys
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one

    Args:
        module_name: Name of the module

    Returns:
        logging.Logger: Logger instance
    """
    logger = logging.getLogger(module_name)

    # Setup logging if not already configured
    if not logger.handlers:
        return setup_logging(module_name)

    return logger


# Pre-configured loggers for common modules
_loggers = {}


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Get or create a module logger with caching

    Args:
        module_name: Name of the module

    Returns:
        logging.Logger: Logger instance
    """
    if module_name not in _loggers:
        _loggers[module_name] = setup_logging(module_name)

    return _loggers[module_name]


# Convenience function for quick logging
def log_message(
    module_name: str,
    level: int,
    message: str,
    exc_info: Optional[Exception] = None
):
    """
    Log a message for a module

    Args:
        module_name: Name of the module
        level: Log level (logging.DEBUG, logging.INFO, etc.)
        message: Message to log
        exc_info: Exception info (optional)
    """
    logger = get_module_logger(module_name)

    if exc_info:
        logger.log(level, message, exc_info=exc_info)
    else:
        logger.log(level, message)


# Logging level shortcuts
def debug(module_name: str, message: str):
    """Log debug message"""
    log_message(module_name, logging.DEBUG, message)


def info(module_name: str, message: str):
    """Log info message"""
    log_message(module_name, logging.INFO, message)


def warning(module_name: str, message: str):
    """Log warning message"""
    log_message(module_name, logging.WARNING, message)


def error(module_name: str, message: str, exc_info: Optional[Exception] = None):
    """Log error message"""
    log_message(module_name, logging.ERROR, message, exc_info)


def critical(module_name: str, message: str, exc_info: Optional[Exception] = None):
    """Log critical message"""
    log_message(module_name, logging.CRITICAL, message, exc_info)


if __name__ == "__main__":
    # Test logging configuration
    logger = setup_logging("test")

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    try:
        raise ValueError("Test exception")
    except Exception as e:
        logger.critical("This is a critical message with exception", exc_info=e)

    print(f"Log file created at: {LOG_DIR / 'test.log'}")
