import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


class CortexLogger:
    """Central logging system for the Cortex package."""

    _instance = None
    _configured = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._configured:
            self._setup_logging()
            self._configured = True

    def _setup_logging(self):
        """Configure the logging system with file rotation."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / "cortex.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Configure cortex logger specifically
        cortex_logger = logging.getLogger("cortex")
        cortex_logger.setLevel(logging.DEBUG)

        # Error file handler for critical issues
        error_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / "cortex_errors.log",
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        cortex_logger.addHandler(error_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for the given name."""
        return logging.getLogger(f"cortex.{name}")


# Global instance
_cortex_logger = CortexLogger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for the cortex package.
    """
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_module = frame.f_back.f_globals.get("__name__", "unknown")
            name = caller_module
        else:
            name = "unknown"

    return _cortex_logger.get_logger(name)


def configure_logging(level: str = "INFO", log_dir: Optional[str] = None):
    """
    Reconfigure logging with custom settings.
    """
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Update all cortex loggers
    cortex_logger = logging.getLogger("cortex")
    cortex_logger.setLevel(numeric_level)

    # Update handlers if needed
    for handler in cortex_logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            if log_dir:
                handler.baseFilename = str(log_path / Path(handler.baseFilename).name)
        handler.setLevel(numeric_level)
