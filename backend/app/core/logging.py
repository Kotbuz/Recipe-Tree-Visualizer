import sys
from pathlib import Path

from loguru import logger

from app.core.config import Settings


def setup_logging(settings: Settings) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app.log",
        level=settings.log_level,
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )
