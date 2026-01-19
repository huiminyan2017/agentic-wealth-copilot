import logging
import os
from pathlib import Path


LOGGER_DIR = Path("data/logs")

def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()

    log_dir = LOGGER_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    handlers = [
        logging.StreamHandler(),  # console
        logging.FileHandler(log_file, encoding="utf-8"),  # file
    ]

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
    )

    logging.getLogger(__name__).info("Logging initialized. File: %s", log_file)