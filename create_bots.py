import asyncio
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from typing import List

def load_bot_tokens() -> List[str]:
    """
    Загружает токены ботов из переменной окружения BOT_TOKENS.

    Формат:
      - значения разделяются запятой (,) и/или переводом строки
      - пробелы вокруг токена игнорируются

    Пример:
      export BOT_TOKENS="123:AAA..., 456:BBB..."
    """
    raw = (os.getenv("BOT_TOKENS") or "").strip()
    if not raw:
        raise RuntimeError(
            "Не найдены токены ботов. Задайте переменную окружения BOT_TOKENS "
            "(токены через запятую) и повторите запуск."
        )

    tokens = [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
    # Минимальная валидация: токен Telegram обычно имеет вид "<число>:<строка>"
    bad = [t for t in tokens if ":" not in t or len(t) < 10]
    if bad:
        raise RuntimeError(
            "Некорректный формат токенов в BOT_TOKENS: "
            + ", ".join(repr(t) for t in bad)
        )
    return tokens

work_channels: List = []

class WorkChannel:
    def __init__(self, token: str):
        self.token = token
        self.bot = None
        self.username = None
        self.update_id = 0
        self.active_chat_id = None

    async def initialize(self):
        self.bot = ApplicationBuilder().token(self.token).build()
        self.bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        await self.bot.initialize()
        await self.bot.start()
        info = await self.bot.bot.get_me()
        self.username = info.username
        print(f"Бот {self.username} инициализирован")

    async def handle_message(self, update):
        chat_id = update.message.chat.id
        user = update.message.from_user.username or update.message.from_user.first_name
        text = update.message.text or "(без текста)"
        chat_type = update.message.chat.type
        self.active_chat_id = chat_id

        print(f"\n{'='*60}")
        print(f"[{self.username}] Получено новое сообщение")
        print(f"  От: @{user}")
        print(f"  Chat ID: {chat_id} ({chat_type})")
        print(f"  Сообщение: {text}")
        print(f"  Время: {update.message.date}")
        print(f"{'='*60}\n")

    async def shutdown(self):
        if self.bot:
            await self.bot.stop()
            await self.bot.shutdown()

async def create_bots():
    global work_channels
    work_channels = []
    for token in load_bot_tokens():
        ch = WorkChannel(token)
        await ch.initialize()
        work_channels.append(ch)
    print(f"Создано {len(work_channels)} ботов")
    return work_channels

async def process_channel(channel, timeout=10):
    print(f"Запущена обработка канала {channel.username}")
    
    while True:
        try:
            updates = await channel.bot.bot.get_updates(
                offset=channel.update_id + 1,
                timeout=timeout,
                allowed_updates=Update.ALL_TYPES
            ) or []
            
            for update in updates:
                if update.message:
                    chat_id = update.message.chat.id
                    channel.active_chat_id = chat_id
                    text = update.message.text or "(без текста)"
                    user = update.message.from_user.username or update.message.from_user.first_name
                    chat_type = update.message.chat.type
                    
                    print(f"\n{'='*60}")
                    print(f"[{channel.username}] Обновление #{update.update_id}")
                    print(f"  От: @{user}")
                    print(f"  Chat ID: {chat_id} ({chat_type})")
                    print(f"  Сообщение: {text}")
                    print(f"  Время: {update.message.date}")
                    print(f"  [{channel.username}] Сообщение обработано")
                    print(f"{'='*60}\n")
                
                channel.update_id = update.update_id
                
        except Exception as e:
            print(f"[ERROR] {channel.username}: {e}")
            await asyncio.sleep(1)

async def main():
    await create_bots()
    print(f"Запускаю обработку {len(work_channels)} каналов параллельно")
    tasks = [asyncio.create_task(process_channel(ch)) for ch in work_channels]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
