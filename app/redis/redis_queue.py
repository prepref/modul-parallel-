import os
import json
import asyncio
import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from app.core.logger import logger

class RedisQueue:
    def __init__(self):
        # В Docker используем имя сервиса 'redis', локально - 'localhost'
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = os.getenv("REDIS_PORT", "6379")
        redis_url = os.getenv("REDIS_URL", f"redis://{redis_host}:{redis_port}")
        self.redis_client = None
        self.queue_name = os.getenv("REDIS_QUEUE", "event_queue")
        self._redis_url = redis_url
        self._max_retries = 10
        self._retry_delay = 2

    async def connect(self, retry=True):
        """Подключается к Redis с повторными попытками"""
        if self.redis_client is not None:
            try:
                await self.redis_client.ping()
                return  # Уже подключен
            except:
                self.redis_client = None
        
        retries = 0
        while retries < self._max_retries:
            try:
                self.redis_client = redis.from_url(
                    self._redis_url,
                    decode_responses=False,  # Получаем bytes для совместимости
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Проверяем подключение
                await self.redis_client.ping()
                logger.info(f"Подключено к Redis: {self._redis_url}")
                return
            except (RedisConnectionError, OSError, Exception) as e:
                retries += 1
                if not retry or retries >= self._max_retries:
                    logger.error(f"Не удалось подключиться после {retries} попыток: {e}")
                    logger.info(f"Redis URL: {self._redis_url}")
                    raise
                logger.warning(f"Попытка подключения {retries}/{self._max_retries}... (ошибка: {e})")
                await asyncio.sleep(self._retry_delay)

    async def disconnect(self):
        """Закрывает соединение с Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Соединение с Redis закрыто")

    async def publish_event(self, event: dict):
        """Публикует событие в очередь Redis"""
        if self.redis_client is None:
            await self.connect()
        
        try:
            # Сериализуем событие в JSON
            data = json.dumps(event, ensure_ascii=False, default=str)
            # Добавляем в очередь Redis
            result = await self.redis_client.rpush(self.queue_name, data.encode('utf-8'))
            update_id = event.get('data', {}).get('update_id', 'N/A')
            messenger = event.get('messenger', 'unknown')
            logger.info(f"Событие добавлено в очередь Redis: {messenger}, update_id={update_id}, очередь={self.queue_name}, длина очереди={result}")
        except (TypeError, ValueError) as e:
            logger.error(f"Ошибка сериализации события в JSON: {e}, event={event}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при публикации события в Redis: {e}", exc_info=True)
            raise