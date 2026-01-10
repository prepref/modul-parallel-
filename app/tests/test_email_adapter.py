"""
Тестовый скрипт для проверки Email адаптера.
Запуск: python -m app.tests.test_email_adapter
"""
import asyncio
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.adapters.email import EmailAdapter
from app.core.logger import logger


class MockRedisQueue:
    """Mock Redis для тестирования"""
    
    def __init__(self):
        self.events = []
    
    async def publish_event(self, event: dict):
        self.events.append(event)
        print("\n📬 Получено письмо:")
        data = event.get("data", {})
        print(f"   От: {data.get('from', 'N/A')}")
        print(f"   Тема: {data.get('subject', 'N/A')}")
        print(f"   Дата: {data.get('date', 'N/A')}")
        body = data.get('body', '')
        if body:
            print(f"   Текст: {body[:100]}...")


async def test_email_connection():
    """Тестирует подключение к IMAP и получение писем"""
    
    # Получаем данные из переменных окружения или запрашиваем
    token = os.getenv("EMAIL_TOKEN")
    
    if not token:
        print("=" * 60)
        print("  ТЕСТ EMAIL АДАПТЕРА")
        print("=" * 60)
        print("\nВведите данные для подключения к IMAP:")
        print("(Для Gmail нужен App Password: https://myaccount.google.com/apppasswords)\n")
        
        host = input("IMAP сервер (imap.gmail.com): ").strip() or "imap.gmail.com"
        port = input("Порт (993): ").strip() or "993"
        username = input("Email: ").strip()
        password = input("Пароль/App Password: ").strip()
        
        if not username or not password:
            print("❌ Email и пароль обязательны!")
            return
        
        token = f"{host}:{port}:{username}:{password}"
    
    print("\n🔄 Подключение к IMAP...")
    
    mock_redis = MockRedisQueue()
    
    try:
        adapter = EmailAdapter(token, mock_redis)
        
        # Тестируем подключение
        adapter._connect()
        print(f"✅ Подключено к {adapter.host}")
        
        # Проверяем наличие писем
        print("\n🔍 Поиск непрочитанных писем...")
        emails = adapter._check_new_emails()
        
        if emails:
            print(f"\n✅ Найдено {len(emails)} новых писем:")
            for email_data in emails:
                await mock_redis.publish_event({"data": email_data})
        else:
            print("📭 Новых писем нет")
        
        adapter._disconnect()
        print("\n✅ Тест завершён успешно!")
        
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        logger.error(f"Детали ошибки: {e}", exc_info=True)


async def test_polling(duration: int = 30):
    """Тестирует polling в течение заданного времени"""
    
    token = os.getenv("EMAIL_TOKEN")
    if not token:
        print("❌ Установите EMAIL_TOKEN в переменных окружения")
        print("   Формат: host:port:username:password")
        return
    
    print(f"\n🔄 Запуск polling на {duration} секунд...")
    print("   Отправьте письмо на указанный email для проверки\n")
    
    mock_redis = MockRedisQueue()
    adapter = EmailAdapter(token, mock_redis)
    
    # Запускаем polling на ограниченное время
    try:
        polling_task = asyncio.create_task(adapter.start_polling())
        await asyncio.sleep(duration)
        polling_task.cancel()
        
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        
        print(f"\n✅ Polling завершён. Получено писем: {len(mock_redis.events)}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Тест Email адаптера")
    parser.add_argument(
        "--mode",
        choices=["connect", "polling"],
        default="connect",
        help="Режим: connect (проверка подключения) или polling (30 сек polling)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Длительность polling в секундах (по умолчанию 30)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "connect":
        asyncio.run(test_email_connection())
    else:
        asyncio.run(test_polling(args.duration))

