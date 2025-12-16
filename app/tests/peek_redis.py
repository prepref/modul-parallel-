import redis
import os

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
queue_name = os.getenv("REDIS_QUEUE", "event_queue")

# Показываем первые 10 элементов очереди
items = r.lrange(queue_name, 0, 9)
for i, item in enumerate(items):
    print(f"[{i}] {item.decode('utf-8')}")
