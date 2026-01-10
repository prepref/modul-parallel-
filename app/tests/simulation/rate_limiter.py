from aiolimiter import AsyncLimiter
from collections import defaultdict

from .limits import TelegramLimits


class MockRateLimiter:
    """
    Имитация rate limiting для тестов:
    - Глобальный лимит (20 req/s)
    - Персональный лимит на каждого бота (1 req/s)
    """
    
    def __init__(self, limits: TelegramLimits = None):
        limits = limits or TelegramLimits()
        
        # Глобальный лимит: N запросов в секунду на весь контейнер
        self.global_limiter = AsyncLimiter(
            max_rate=limits.APP_GLOBAL_RPS,
            time_period=1.0
        )
        
        # Персональные лимитеры: по N запросов/сек на бота
        self._per_bot_rps = limits.APP_PER_BOT_RPS
        self._bot_limiters: dict[int, AsyncLimiter] = defaultdict(
            lambda: AsyncLimiter(max_rate=self._per_bot_rps, time_period=1.0)
        )
        
        # Статистика
        self.total_waits = 0
        self.global_waits = 0
        self.bot_waits = 0
    
    async def acquire(self, bot_id: int):
        """
        Получает разрешение на запрос.
        Сначала глобальный лимит, затем персональный.
        """
        self.total_waits += 1
        
        async with self.global_limiter:
            self.global_waits += 1
            
            async with self._bot_limiters[bot_id]:
                self.bot_waits += 1
    
    def get_stats(self) -> dict:
        """Возвращает статистику rate limiter"""
        return {
            "total_waits": self.total_waits,
            "global_waits": self.global_waits,
            "bot_waits": self.bot_waits,
            "active_bots": len(self._bot_limiters),
        }

