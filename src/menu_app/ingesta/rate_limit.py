from __future__ import annotations

import random
import threading
import time


class RateLimiter:
    """Espacia llamadas HTTP consecutivas para ser un buen ciudadano con el servidor.

    Pensado para un cliente HTTP usado desde un solo hilo/proceso a la vez; el
    lock solo protege contra el caso de que en el futuro se paralelice.
    """

    def __init__(self, min_interval_seconds: float, jitter_seconds: float = 0.0) -> None:
        self._min_interval = min_interval_seconds
        self._jitter = jitter_seconds
        self._lock = threading.Lock()
        self._last_call_at: float | None = None

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last_call_at is not None:
                elapsed = now - self._last_call_at
                target = self._min_interval + random.uniform(0, self._jitter)
                remaining = target - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            self._last_call_at = time.monotonic()
