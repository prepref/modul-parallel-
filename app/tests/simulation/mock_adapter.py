import asyncio
import time

from app.redis.redis_queue import RedisQueue
from app.core.logger import logger

from .api_simulator import TelegramAPISimulator
from .exceptions import RetryAfterError, TimedOutError
from .rate_limiter import MockRateLimiter


class RealisticMockAdapter:
    """
    Mock-адаптер с симуляцией Telegram API.
    Используется для нагрузочного тестирования.
    """
    
    # Глобальный семафор для всех адаптеров
    _connection_semaphore: asyncio.Semaphore = None
    # Глобальный rate limiter для всех адаптеров
    _rate_limiter: MockRateLimiter = None
    
    def __init__(self, bot_id: int, redis_queue: RedisQueue, api_simulator: TelegramAPISimulator,
        connection_semaphore: asyncio.Semaphore = None, rate_limiter: MockRateLimiter = None
    ):
        self.bot_id = bot_id
        self.redis = redis_queue
        self.api = api_simulator
        
        if connection_semaphore:
            RealisticMockAdapter._connection_semaphore = connection_semaphore
        
        if rate_limiter:
            RealisticMockAdapter._rate_limiter = rate_limiter
        
        self.last_activity = time.monotonic()
        
        # Статистика
        self.events_sent = 0
        self.rate_limits_hit = 0
        self.timeouts = 0
        self.errors = 0
        self.semaphore_waits = 0
        
        # Статистика таймаутов
        self.timeout_values: list[float] = []
    
    def get_dynamic_timeout(self) -> float:
        """
        Динамический timeout: чем дольше бот неактивен, тем больше timeout (до 60 сек).
        При активности timeout минимален (1 сек) для быстрой реакции.
        """
        idle_time = time.monotonic() - self.last_activity
        timeout = max(1.0, min(60.0, idle_time))
        return round(timeout, 1)
    
    async def start_polling(self, duration_seconds: int = 60):
        """Запускает polling на заданное время"""
        start_time = time.monotonic()
        
        while time.monotonic() - start_time < duration_seconds:
            # Вычисляем динамический таймаут
            timeout = int(self.get_dynamic_timeout())
            self.timeout_values.append(timeout)
            
            try:
                if self._connection_semaphore:
                    self.semaphore_waits += 1
                    async with self._connection_semaphore:
                        if self._rate_limiter:
                            await self._rate_limiter.acquire(self.bot_id)
                        updates = await self.api.get_updates(timeout=timeout)
                else:
                    if self._rate_limiter:
                        await self._rate_limiter.acquire(self.bot_id)
                    updates = await self.api.get_updates(timeout=timeout)
                
                for update in updates:
                    await self._publish_update(update)

                    self.last_activity = time.monotonic()
                    
            except RetryAfterError as e:
                self.rate_limits_hit += 1

                retry_after = e.retry_after + 1
                logger.warning(f"Bot {self.bot_id}: RetryAfter {retry_after}s")
                await asyncio.sleep(retry_after)
                
            except TimedOutError:
                self.timeouts += 1
                
            except ConnectionError as e:
                self.errors += 1
                logger.error(f"Bot {self.bot_id}: {e}")
                await asyncio.sleep(3)
                
            except Exception as e:
                self.errors += 1
                logger.error(f"Bot {self.bot_id}: {e}")
                await asyncio.sleep(5)
    
    async def _publish_update(self, update: dict):
        """Публикует обновление в Redis"""
        await self.redis.publish_event({
            "messenger": "telegram",
            "token": f"mock_token_{self.bot_id}",
            "data": update
        })
        self.events_sent += 1
    
    def get_stats(self) -> dict:
        """Возвращает статистику адаптера"""
        return {
            "bot_id": self.bot_id,
            "events_sent": self.events_sent,
            "rate_limits_hit": self.rate_limits_hit,
            "timeouts": self.timeouts,
            "errors": self.errors,
            "timeout_values": self.timeout_values,
        }
    
    def get_timeout_stats(self) -> dict:
        """Возвращает статистику динамических таймаутов"""
        if not self.timeout_values:
            return {"min": 0, "max": 0, "avg": 0, "count": 0}
        
        return {
            "min": min(self.timeout_values),
            "max": max(self.timeout_values),
            "avg": sum(self.timeout_values) / len(self.timeout_values),
            "count": len(self.timeout_values),
        }

