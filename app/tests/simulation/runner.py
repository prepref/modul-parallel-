import asyncio
import time
from datetime import datetime

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from app.redis.redis_queue import RedisQueue

from .limits import TelegramLimits
from .api_simulator import TelegramAPISimulator
from .mock_adapter import RealisticMockAdapter
from .rate_limiter import MockRateLimiter


async def run_realistic_test(num_bots: int = 40, duration_seconds: int = 60, 
    limits: TelegramLimits = None, use_semaphore: bool = True, use_rate_limit: bool = True
) -> dict:
    """
    Запускает нагрузочное тестирование.
    
    Args:
        num_bots: Количество имитируемых ботов
        duration_seconds: Длительность теста в секундах
        limits: Кастомные лимиты (опционально)
        use_semaphore: Использовать Semaphore для ограничения соединений
        use_rate_limit: Использовать Rate Limiting
    
    Returns:
        Словарь с результатами теста
    """
    limits = limits or TelegramLimits()
    
    _print_header(num_bots, duration_seconds, limits, use_semaphore, use_rate_limit)
    
    # Метрики ресурсов
    process = _get_process()
    start_memory = _get_memory(process)
    start_time = time.monotonic()
    
    redis = RedisQueue()
    await redis.connect()
    
    api_simulator = TelegramAPISimulator(limits)
    
    connection_semaphore = None
    if use_semaphore:
        connection_semaphore = asyncio.Semaphore(limits.APP_MAX_CONCURRENT)
    
    rate_limiter = None
    if use_rate_limit:
        rate_limiter = MockRateLimiter(limits)
    
    bots = [
        RealisticMockAdapter(i, redis, api_simulator, connection_semaphore, rate_limiter)
        for i in range(num_bots)
    ]
    
    print(f"[{_now()}] Запуск {num_bots} ботов (Semaphore: {use_semaphore}, RateLimit: {use_rate_limit})...\n")
    
    tasks = [
        asyncio.create_task(bot.start_polling(duration_seconds))
        for bot in bots
    ]
    
    monitor_task = asyncio.create_task(
        _monitor_loop(process, api_simulator, duration_seconds)
    )
    
    await asyncio.gather(*tasks)
    monitor_task.cancel()
    
    elapsed = time.monotonic() - start_time
    end_memory = _get_memory(process)
    queue_length = await redis.redis_client.llen(redis.queue_name)
    
    await redis.disconnect()
    
    results = _collect_results(
        bots, api_simulator, elapsed,
        start_memory, end_memory, queue_length,
        use_semaphore, use_rate_limit, rate_limiter
    )
    
    _print_results(results)
    
    return results


def _print_header(num_bots: int, duration: int, limits: TelegramLimits, use_semaphore: bool, use_rate_limit: bool):
    """Выводит заголовок теста"""
    print(f"\n{'='*70}")
    print(f"  РЕАЛИСТИЧНОЕ ТЕСТИРОВАНИЕ: {num_bots} ботов, {duration} сек")
    print(f"  Лимиты API: {limits.MAX_REQUESTS_PER_SECOND} req/s, "
          f"{limits.MAX_CONCURRENT_CONNECTIONS} connections")
    if use_semaphore:
        print(f"  Semaphore: ✅ Включён (макс. {limits.APP_MAX_CONCURRENT} одновременно)")
    else:
        print("  Semaphore: ❌ Выключен")
    if use_rate_limit:
        print(f"  Rate Limit: ✅ Включён ({limits.APP_GLOBAL_RPS} req/s глобально, "
              f"{limits.APP_PER_BOT_RPS} req/s на бота)")
    else:
        print("  Rate Limit: ❌ Выключен")
    print(f"{'='*70}\n")


def _print_results(results: dict):
    """Выводит результаты теста"""
    print(f"\n{'='*70}")
    print("  РЕЗУЛЬТАТЫ")
    print(f"{'='*70}")
    print(f"  Ботов:                    {results['bots']}")
    print(f"  Semaphore:                {'✅ Вкл' if results['use_semaphore'] else '❌ Выкл'}")
    print(f"  Rate Limit:               {'✅ Вкл' if results['use_rate_limit'] else '❌ Выкл'}")
    print(f"  Время теста:              {results['duration']:.1f} сек")
    print(f"  Событий отправлено:       {results['events_sent']}")
    print(f"  События/сек:              {results['events_per_sec']:.1f}")
    print(f"  Очередь Redis:            {results['queue_length']}")
    print()
    print("  --- API Симулятор ---")
    print(f"  Всего запросов:           {results['api_requests']}")
    print(f"  Rate limit (429):         {results['api_rate_limits']}")
    print(f"  Таймауты:                 {results['api_timeouts']}")
    print(f"  Сетевые ошибки:           {results['api_network_errors']}")
    print()
    ts = results['timeout_stats']
    print("  --- Динамический таймаут ---")
    print(f"  Мин / Макс / Среднее:     {ts['min']:.0f} / {ts['max']:.0f} / {ts['avg']:.1f} сек")
    print(f"  Всего замеров:            {ts['count']}")
    
    # Rate limiter статистика
    if results.get('rate_limit_stats'):
        rls = results['rate_limit_stats']
        print()
        print("  --- App Rate Limiter ---")
        print(f"  Всего ожиданий:           {rls['total_waits']}")
        print(f"  Активных ботов:           {rls['active_bots']}")
    
    print()
    print("  --- Ресурсы ---")
    print(f"  RAM начало/конец:         {results['memory_start']:.0f} → {results['memory_end']:.0f} MB")
    print(f"  Рост RAM:                 {results['memory_growth']:.1f} MB")
    print(f"{'='*70}\n")


def _collect_results(bots: list, api: TelegramAPISimulator, elapsed: float, start_mem: float, end_mem: float,
    queue_len: int, use_semaphore: bool, use_rate_limit: bool, rate_limiter
) -> dict:
    """Собирает результаты теста"""
    total_events = sum(b.events_sent for b in bots)
    total_rate_limits = sum(b.rate_limits_hit for b in bots)
    total_errors = sum(b.errors for b in bots)
    
    api_stats = api.get_stats()
    
    # Собираем статистику динамических таймаутов
    all_timeouts = []
    for bot in bots:
        all_timeouts.extend(bot.timeout_values)
    
    if all_timeouts:
        timeout_stats = {
            "min": min(all_timeouts),
            "max": max(all_timeouts),
            "avg": sum(all_timeouts) / len(all_timeouts),
            "count": len(all_timeouts),
        }
    else:
        timeout_stats = {"min": 0, "max": 0, "avg": 0, "count": 0}
    
    # Статистика rate limiter
    rate_limit_stats = None
    if rate_limiter:
        rate_limit_stats = rate_limiter.get_stats()
    
    return {
        "bots": len(bots),
        "use_semaphore": use_semaphore,
        "use_rate_limit": use_rate_limit,
        "duration": elapsed,
        "events_sent": total_events,
        "events_per_sec": total_events / elapsed if elapsed > 0 else 0,
        "queue_length": queue_len,
        "bot_rate_limits": total_rate_limits,
        "bot_errors": total_errors,
        "api_requests": api_stats["total_requests"],
        "api_rate_limits": api_stats["rate_limit_hits"],
        "api_timeouts": api_stats["timeouts"],
        "api_network_errors": api_stats["network_errors"],
        "memory_start": start_mem,
        "memory_end": end_mem,
        "memory_growth": end_mem - start_mem,
        "timeout_stats": timeout_stats,
        "rate_limit_stats": rate_limit_stats,
    }


async def _monitor_loop(process, api: TelegramAPISimulator, duration: int):
    """Выводит метрики каждые 10 секунд"""
    try:
        intervals = duration // 10
        for i in range(intervals):
            await asyncio.sleep(10)
            mem = _get_memory(process)
            conns = api.active_connections
            max_conns = api.limits.MAX_CONCURRENT_CONNECTIONS
            print(f"  [{(i+1)*10:3}s] RAM: {mem:.0f}MB | "
                  f"Connections: {conns}/{max_conns} | "
                  f"429s: {api.rate_limit_hits}")
    except asyncio.CancelledError:
        pass


def _get_process():
    """Возвращает текущий процесс для мониторинга"""
    if HAS_PSUTIL:
        return psutil.Process()
    return None


def _get_memory(process) -> float:
    """Возвращает использование памяти в MB"""
    if process and HAS_PSUTIL:
        return process.memory_info().rss / 1024 / 1024
    return 0.0


def _now() -> str:
    """Текущее время"""
    return datetime.now().strftime('%H:%M:%S')

