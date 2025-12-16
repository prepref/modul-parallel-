from aiolimiter import AsyncLimiter
from collections import defaultdict
from typing import Coroutine, Any

# Глобальный лимит: 20 запросов в секунду на весь контейнер
# Telegram лимит: 30 req/sec, используем 20 для безопасности
global_limiter = AsyncLimiter(max_rate=20, time_period=1.0)

# Персональные лимитеры: по 1 запросу/сек на токен
_bot_limiters = defaultdict(lambda: AsyncLimiter(max_rate=1, time_period=1.0))

async def with_rate_limit(coro: Coroutine[Any, Any, Any], token: str = None):
    """
    Применяет rate limiting к корутине.
    Сначала проходит через глобальный лимитер,
    затем через лимитер для конкретного токена (если указан).
    
    Args:
        coro: Корутина для выполнения
        token: Опциональный токен бота для персонального лимита
    
    Returns:
        Результат выполнения корутины
    """
    async with global_limiter:
        if token:
            async with _bot_limiters[token]:
                return await coro
        else:
            return await coro
