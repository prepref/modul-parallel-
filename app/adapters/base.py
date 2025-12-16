from abc import ABC, abstractmethod

import time

class BaseAdapter(ABC):
    def __init__(self, token: str, redis_queue):
        super().__init__()
        self.token = token
        self.redis = redis_queue
        self.last_activity = time.monotonic()

    @abstractmethod
    async def start_polling(self):
        """Запускает основной polling-цикл"""
        pass

    def get_dynamic_timeout(self) -> float:
        idle_time = time.monotonic() - self.last_activity
        timeout = max(1.0, min(30.0, idle_time))
        return round(timeout, 1)