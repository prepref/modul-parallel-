from dataclasses import dataclass


@dataclass
class TelegramLimits:
    """
    Близкие к реальным лимитам Telegram Bot API.
    Используются для реалистичной симуляции поведения API.
    """
    # Лимит запросов в секунду на один токен
    MAX_REQUESTS_PER_SECOND: int = 30
    
    # Максимум одновременных long-poll соединений с одного IP (Telegram)
    MAX_CONCURRENT_CONNECTIONS: int = 30
    
    # Наш внутренний лимит (Semaphore) — меньше чем Telegram для запаса
    APP_MAX_CONCURRENT: int = 25
    
    # Rate limit приложения
    APP_GLOBAL_RPS: int = 20       # Глобальный лимит req/s
    APP_PER_BOT_RPS: float = 1.0   # Лимит req/s на каждого бота
    
    # Диапазон RetryAfter при 429
    RETRY_AFTER_MIN: int = 5
    RETRY_AFTER_MAX: int = 60
    
    # Вероятности ошибок (для симуляции)
    RATE_LIMIT_PROBABILITY: float = 0.02      # 429 при высокой нагрузке
    TIMEOUT_PROBABILITY: float = 0.05          # Таймаут long polling
    NETWORK_ERROR_PROBABILITY: float = 0.01    # Сетевая ошибка

