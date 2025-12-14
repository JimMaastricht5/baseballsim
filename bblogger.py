# --- Copyright Notice ---
# Copyright (c) 2024 Jim Maastricht
"""
--- File Context and Purpose ---

FILE: bblogger.py (Implied)
DESCRIPTION: Configures and manages the logging system for the baseball
simulation application using the loguru library. It sets up handlers for both
console (stderr) output and file logging (logs/baseball_sim.log).

PRIMARY FUNCTION:
- configure_logger(): Initializes or reconfigures the loguru logger with a
  specified logging level, ensuring logs are written to the console and a file.

EXPORTS:
- logger: The configured loguru logger instance.
- configure_logger: The function to adjust logging levels at runtime.

Contact: JimMaastricht5@gmail.com
"""

from loguru import logger
import sys
import os

# IDs for handlers to enable removal/reconfiguration
console_handler_id = None
file_handler_id = None

def configure_logger(log_level="INFO"):
    """
    Configure the logger with the specified log level
    
    :param log_level: The logging level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    :return: None
    """
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
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file handler
    file_handler_id = logger.add(
        "logs/baseball_sim.log", 
        rotation="1 MB", 
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )

# Initialize with default level
configure_logger("INFO")

# Export logger and configuration function
__all__ = ["logger", "configure_logger"]