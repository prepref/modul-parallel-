"""
Тест: Email адаптер → Redis очередь
Запуск: python -m app.tests.test_email_redis
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.adapters.email import EmailAdapter
from app.redis.redis_queue import RedisQueue


async def test_email_to_redis():
    """Тестирует доставку писем в Redis"""
    
    token = os.getenv("EMAIL_TOKEN")
    
    if not token:
        print("=" * 60)
        print("  ТЕСТ: EMAIL → REDIS")
        print("=" * 60)
        print("\nВведите данные для подключения:")
        
        host = input("IMAP сервер (imap.gmail.com): ").strip() or "imap.gmail.com"
        port = input("Порт (993): ").strip() or "993"
        username = input("Email: ").strip()
        password = input("App Password: ").strip()
        
        if not username or not password:
            print("❌ Email и пароль обязательны!")
            return
        
        token = f"{host}:{port}:{username}:{password}"
    
    # Подключаемся к Redis
    print("\n🔄 Подключение к Redis...")
    redis = RedisQueue()
    
    try:
        await redis.connect()
        print("✅ Redis подключён")
    except Exception as e:
        print(f"❌ Ошибка подключения к Redis: {e}")
        print("   Убедитесь что Redis запущен: docker start redis")
        return
    
    # Проверяем очередь ДО теста
    queue_before = await redis.redis_client.llen(redis.queue_name)
    print(f"📊 Очередь до теста: {queue_before} событий")
    
    # Создаём адаптер
    print("\n🔄 Подключение к IMAP...")
    try:
        adapter = EmailAdapter(token, redis)
        adapter._connect()
        print(f"✅ IMAP подключён: {adapter.host}")
    except Exception as e:
        print(f"❌ Ошибка IMAP: {e}")
        await redis.disconnect()
        return
    
    # Проверяем письма и публикуем в Redis
    print("\n🔍 Поиск новых писем...")
    emails = adapter._check_new_emails()
    
    if not emails:
        print("📭 Новых писем нет")
        adapter._disconnect()
        await redis.disconnect()
        return
    
    print(f"✅ Найдено {len(emails)} писем")
    print("\n📤 Отправка в Redis...")
    
    sent = 0
    for email_data in emails:
        try:
            await redis.publish_event({
                "messenger": "email",
                "token": token[:30] + "...",
                "data": email_data
            })
            sent += 1
            print(f"   ✓ {email_data.get('subject', 'N/A')[:50]}")
        except Exception as e:
            print(f"   ✗ Ошибка: {e}")
    
    # Проверяем очередь ПОСЛЕ теста
    queue_after = await redis.redis_client.llen(redis.queue_name)
    
    print("\n" + "=" * 60)
    print("  РЕЗУЛЬТАТЫ")
    print("=" * 60)
    print(f"  Писем найдено:      {len(emails)}")
    print(f"  Отправлено в Redis: {sent}")
    print(f"  Очередь до/после:   {queue_before} → {queue_after}")
    print(f"  Добавлено:          +{queue_after - queue_before}")
    print("=" * 60)
    
    if queue_after > queue_before:
        print("\n✅ ТЕСТ ПРОЙДЕН: Письма успешно доставлены в Redis!")
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕН: Письма не добавлены в очередь")
    
    adapter._disconnect()
    await redis.disconnect()


if __name__ == "__main__":
    asyncio.run(test_email_to_redis())

