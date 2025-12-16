import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Уровень логирования из переменной окружения (по умолчанию INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = Path("/app/logs")
LOG_FILE = LOG_DIR / "bot_aggregator.log"

# Создаем директорию для логов, если её нет
LOG_DIR.mkdir(exist_ok=True)


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
    
    # Удаляем существующие обработчики, чтобы избежать дублирования
    logger.handlers.clear()
    
    # Формат логов
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
        # Если не удалось создать файловый обработчик, продолжаем без него
        # Используем print, так как logger еще не полностью настроен
        print(f"WARNING: Не удалось создать файловый обработчик логов: {e}", file=sys.stderr)
    
    return logger


# Глобальный логгер для использования в других модулях
logger = setup_logger()

