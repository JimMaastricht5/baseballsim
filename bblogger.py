# Copyright (c) 2024 Jim Maastricht
"""
Logging configuration using loguru. Sets up console and file handlers (logs/baseball_sim.log).
Exports: logger, configure_logger.
"""

from loguru import logger
import sys
import os

# Reconfigure standard streams to UTF-8 on Windows to prevent UnicodeEncodeError
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# IDs for handlers to enable removal/reconfiguration
console_handler_id = None
file_handler_id = None


def configure_logger(log_level="INFO"):
    """Configure or reconfigure the logger with console and file handlers at the given level."""
    global console_handler_id, file_handler_id

    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Remove existing handlers if they exist
    if console_handler_id is not None:
        logger.remove(console_handler_id)
    if file_handler_id is not None:
        logger.remove(file_handler_id)
    elif logger._core.handlers:  # Remove default handler on first run
        logger.remove()

    # Add console handler
    console_handler_id = logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # Add file handler
    file_handler_id = logger.add(
        "logs/baseball_sim.log",
        rotation="1 MB",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


# Initialize with default level
configure_logger("INFO")

# Export logger and configuration function
__all__ = ["logger", "configure_logger"]
