import asyncio

from app.config import load_bots_from_env
from app.adapters.telegram import TelegramAdapter
from app.redis.redis_queue import RedisQueue
from app.core.logger import logger

async def main():
    logger.info("=" * 70)
    logger.info("Запуск системы обработки событий ботов")
    logger.info("=" * 70)
    
    # Загружаем конфигурацию ботов
    bots = load_bots_from_env()
    logger.info(f"Загружено ботов: {len(bots)}")
    
    if not bots:
        logger.error("Не найдено ни одного бота в конфигурации!")
        logger.info("Убедитесь, что в .env файле есть переменные BOT_1, BOT_2 и т.д.")
        return
    
    # Инициализируем Redis
    logger.info("Подключение к Redis...")
    redis = RedisQueue()
    try:
        await redis.connect()
        logger.info("Подключение к Redis установлено")
    except Exception as e:
        logger.error(f"Не удалось подключиться к Redis: {e}", exc_info=True)
        logger.error("Проверьте, что Redis запущен и доступен")
        return
    
    # Создаем задачи для каждого бота
    tasks = []
    for bot in bots:
        if bot.messenger == "telegram":
            adapter = TelegramAdapter(bot.token, redis)
            tasks.append(asyncio.create_task(adapter.start_polling()))
            logger.info(f"Запущен бот {bot.messenger}:{bot.token[:10]}...")
        else:
            logger.warning(f"Мессенджер {bot.messenger} не поддерживается!")
    
    if not tasks:
        logger.error("Не удалось запустить ни одного бота!")
        await redis.disconnect()
        return
    
    logger.info(f"Запущено {len(tasks)} задач обработки")
    logger.info("=" * 70)
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await redis.disconnect()
        logger.info("Все соединения закрыты")

if __name__ == "__main__":
    asyncio.run(main())