import logging
from pathlib import Path

from .settings import settings


def configure_logging() -> None:
    level = settings.log_level.upper()

    log_dir = Path(settings.logs_dir)
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