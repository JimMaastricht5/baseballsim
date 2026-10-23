# Copyright (c) 2024 Jim Maastricht
"""
Logging configuration using loguru. Sets up console and file handlers (logs/baseball_sim_<timestamp>.log).
Each process logs to its own timestamped file, rolling over to a new file at 1 MB, and only the newest files are kept.
A shared fixed file name can't be rotated on Windows while another process (e.g. the UI) has it open, which flooded
the console with "Logging error in Loguru Handler" blocks.
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


LOG_FILE_NAME = "baseball_sim_{time:YYYY-MM-DD_HH-mm-ss_SSSSSS}.log"  # {time} makes every rollover a new file
LOG_ROTATION = "1 MB"
LOG_RETENTION = 20  # newest files kept, only files matching LOG_FILE_NAME are ever removed


def configure_logger(
    log_level="INFO", log_dir="logs", rotation=LOG_ROTATION, retention=LOG_RETENTION, console_level=None
):
    """
    Configure or reconfigure the logger with console and file handlers at the given level.
    console_level sets a different level for the console only, e.g. "WARNING" keeps INFO in the file but off screen.
    """
    global console_handler_id, file_handler_id

    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

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
        level=console_level or log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # Add file handler
    file_handler_id = logger.add(
        os.path.join(log_dir, LOG_FILE_NAME),
        rotation=rotation,
        retention=retention,
        delay=True,  # create the file on the first message, so programs that never log don't leave empty files
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


# Initialize with default level
configure_logger("INFO")

# Export logger and configuration function
__all__ = ["logger", "configure_logger"]
