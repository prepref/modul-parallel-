class RetryAfterError(Exception):
    """Имитация Telegram RetryAfter (429 Too Many Requests)"""
    
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Flood control: retry after {retry_after} seconds")


class TimedOutError(Exception):
    """Имитация таймаута long polling"""
    pass

