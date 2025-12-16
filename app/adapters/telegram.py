import asyncio
import time

from app.adapters.base import BaseAdapter
from app.core.rate_limit import with_rate_limit
from app.core.logger import logger

from telegram import Bot
from telegram.error import TelegramError


class TelegramAdapter(BaseAdapter):
    def __init__(self, token, redis_queue):
        super().__init__(token, redis_queue)
        self.last_activity = time.monotonic()
        self.bot = Bot(token=self.token)
        self.offset = None

    async def start_polling(self):
        bot_id = self.token[:10]
        logger.info(f"Стартую polling для бота: {bot_id}...")
        
        try:
            await self.bot.delete_webhook(drop_pending_updates=True)
            logger.info(f"Webhook удален для бота: {bot_id}...")
        except Exception as e:
            logger.warning(f"Ошибка при удалении webhook для бота {bot_id}: {e}")

        while True:
            timeout = int(self.get_dynamic_timeout())
            try: 
                # Применяем rate limiting к запросу get_updates
                updates = await with_rate_limit(
                    self.bot.get_updates(
                        offset=self.offset,
                        timeout=timeout,
                        limit=100
                    ),
                    token=self.token
                )

                if updates:
                    logger.info(f"Получено {len(updates)} обновлений для бота: {bot_id}...")
                
                for update in updates:
                    try:
                        # Публикуем событие в Redis
                        await self.redis.publish_event({
                            "messenger": "telegram",
                            "token": self.token,
                            "data": update.to_dict()
                        })
                        self.last_activity = time.monotonic()
                        # Обновляем offset для следующего запроса
                        self.offset = update.update_id + 1
                    except Exception as e:
                        logger.error(f"Ошибка при публикации обновления {update.update_id} в Redis: {e}", exc_info=True)
                        # Продолжаем обработку следующих обновлений
                        continue
        
            except TelegramError as e:
                logger.error(f"Telegram API error для бота {bot_id}: {e}")
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                logger.info(f"Остановка polling для бота: {bot_id}...")
                break
            except Exception as e:
                logger.error(f"Ошибка polling для бота {bot_id}: {e}", exc_info=True)
                await asyncio.sleep(5)