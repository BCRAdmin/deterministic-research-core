from __future__ import annotations

import time


class SecRateLimiter:
    def __init__(self, request_delay_seconds: float = 0.11):
        self.request_delay_seconds = request_delay_seconds
        self._last_request_ts = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self._last_request_ts
        wait = self.request_delay_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.time()
