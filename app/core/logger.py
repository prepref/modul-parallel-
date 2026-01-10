import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

if Path("/app/logs").exists() or os.getenv("RUNNING_IN_DOCKER"):
    LOG_DIR = Path("/app/logs")
else:
    LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"

LOG_FILE = LOG_DIR / "bot_aggregator.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger(name: str = "bot_aggregator") -> logging.Logger:
    """
    Настраивает и возвращает логгер с консольным и файловым выводом
    
    Args:
        name: Имя логгера
    
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    
    logger.handlers.clear()
    
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Консольный обработчик (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик с ротацией (10MB, 5 файлов)
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"WARNING: Не удалось создать файловый обработчик логов: {e}", file=sys.stderr)
    
    return logger


logger = setup_logger()

