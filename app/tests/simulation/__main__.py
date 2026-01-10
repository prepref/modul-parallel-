"""
Запуск нагрузочного тестирования.

Использование:
    python -m app.tests.simulation
    python -m app.tests.simulation --bots 100 --duration 120
    python -m app.tests.simulation --bots 200 --no-semaphore  # для сравнения
    python -m app.tests.simulation --bots 200 --no-rate-limit  # без rate limit
"""
import asyncio
import argparse

from .limits import TelegramLimits
from .runner import run_realistic_test


def parse_args():
    parser = argparse.ArgumentParser(
        description="Нагрузочное тестирование системы агрегации ботов"
    )
    parser.add_argument(
        "--bots", "-b",
        type=int,
        default=40,
        help="Количество имитируемых ботов (по умолчанию: 40)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Длительность теста в секундах (по умолчанию: 60)"
    )
    parser.add_argument(
        "--max-rps",
        type=int,
        default=30,
        help="Макс. запросов в секунду API (по умолчанию: 30)"
    )
    parser.add_argument(
        "--max-connections",
        type=int,
        default=30,
        help="Макс. одновременных соединений API (по умолчанию: 30)"
    )
    parser.add_argument(
        "--app-max-concurrent",
        type=int,
        default=25,
        help="Лимит Semaphore в приложении (по умолчанию: 25)"
    )
    parser.add_argument(
        "--app-global-rps",
        type=int,
        default=20,
        help="Глобальный rate limit приложения (по умолчанию: 20 req/s)"
    )
    parser.add_argument(
        "--app-per-bot-rps",
        type=float,
        default=1.0,
        help="Rate limit на каждого бота (по умолчанию: 1.0 req/s)"
    )
    parser.add_argument(
        "--no-semaphore",
        action="store_true",
        help="Отключить Semaphore (для сравнения)"
    )
    parser.add_argument(
        "--no-rate-limit",
        action="store_true",
        help="Отключить Rate Limit (для сравнения)"
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    
    limits = TelegramLimits(
        MAX_REQUESTS_PER_SECOND=args.max_rps,
        MAX_CONCURRENT_CONNECTIONS=args.max_connections,
        APP_MAX_CONCURRENT=args.app_max_concurrent,
        APP_GLOBAL_RPS=args.app_global_rps,
        APP_PER_BOT_RPS=args.app_per_bot_rps,
    )
    
    await run_realistic_test(
        num_bots=args.bots,
        duration_seconds=args.duration,
        limits=limits,
        use_semaphore=not args.no_semaphore,
        use_rate_limit=not args.no_rate_limit
    )


if __name__ == "__main__":
    asyncio.run(main())

