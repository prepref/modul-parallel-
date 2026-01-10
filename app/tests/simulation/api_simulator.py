import asyncio
import time
import random

from .limits import TelegramLimits
from .exceptions import RetryAfterError, TimedOutError


class TelegramAPISimulator:
    """
    Симулятор Telegram Bot API с реалистичными лимитами.
    Имитирует поведение реального API при высокой нагрузке.
    """
    
    def __init__(self, limits: TelegramLimits = None):
        self.limits = limits or TelegramLimits()
        self._request_times: list[float] = []
        self._active_connections = 0
        self._connection_semaphore = asyncio.Semaphore(self.limits.MAX_CONCURRENT_CONNECTIONS)
        self._lock = asyncio.Lock()
        
        # Статистика
        self.total_requests = 0
        self.rate_limit_hits = 0
        self.timeouts = 0
        self.network_errors = 0
    
    @property
    def active_connections(self) -> int:
        return self._active_connections
    
    async def get_updates(self, timeout: int = 30) -> list:
        """
        Имитация getUpdates с реальным поведением:
        - Ограничение одновременных соединений
        - Rate limiting (429)
        - Таймауты
        - Сетевые ошибки
        """
        
        if self._active_connections >= self.limits.MAX_CONCURRENT_CONNECTIONS:
            self.rate_limit_hits += 1
            retry_after = random.randint(
                self.limits.RETRY_AFTER_MIN,
                self.limits.RETRY_AFTER_MAX
            )
            raise RetryAfterError(retry_after)
        
        async with self._connection_semaphore:
            self._active_connections += 1
            try:
                return await self._simulate_request(timeout)
            finally:
                self._active_connections -= 1
    
    async def _simulate_request(self, timeout: int) -> list:
        """Внутренняя логика запроса"""
        self.total_requests += 1
        
        await self._check_rate_limit()
        
        if random.random() < self.limits.TIMEOUT_PROBABILITY:
            self.timeouts += 1
            await asyncio.sleep(timeout)
            raise TimedOutError()
        
        if random.random() < self.limits.NETWORK_ERROR_PROBABILITY:
            self.network_errors += 1
            raise ConnectionError("Connection reset by peer")
        
        # Определяем, будут ли обновления
        num_updates = random.choices(
            [0, 1, 2, 3, 4, 5],
            weights=[50, 25, 12, 7, 4, 2]
        )[0]
        
        if num_updates > 0:
            # Есть обновления — возвращаем быстро (5-20% от timeout)
            wait_time = random.uniform(timeout * 0.05, timeout * 0.2)
        else:
            # Нет обновлений — ждём дольше (30-80% от timeout)
            wait_time = random.uniform(timeout * 0.3, timeout * 0.8)
        
        await asyncio.sleep(wait_time)
        
        return [
            {"update_id": int(time.time() * 1000) + i}
            for i in range(num_updates)
        ]
    
    async def _check_rate_limit(self):
        """Проверяет rate limit по запросам в секунду"""
        now = time.monotonic()
        
        async with self._lock:
            self._request_times = [
                t for t in self._request_times
                if now - t < 1.0
            ]
            
            # Жёсткий лимит
            if len(self._request_times) >= self.limits.MAX_REQUESTS_PER_SECOND:
                self.rate_limit_hits += 1
                retry_after = random.randint(self.limits.RETRY_AFTER_MIN, 30)
                raise RetryAfterError(retry_after)
            
            # Случайный 429 при высокой нагрузке
            load_factor = len(self._request_times) / self.limits.MAX_REQUESTS_PER_SECOND
            if load_factor > 0.7:
                if random.random() < self.limits.RATE_LIMIT_PROBABILITY * load_factor:
                    self.rate_limit_hits += 1
                    retry_after = random.randint(self.limits.RETRY_AFTER_MIN, 15)
                    raise RetryAfterError(retry_after)
            
            self._request_times.append(now)
    
    def get_stats(self) -> dict:
        """Возвращает статистику симулятора"""
        return {
            "total_requests": self.total_requests,
            "rate_limit_hits": self.rate_limit_hits,
            "timeouts": self.timeouts,
            "network_errors": self.network_errors,
            "active_connections": self._active_connections,
        }

