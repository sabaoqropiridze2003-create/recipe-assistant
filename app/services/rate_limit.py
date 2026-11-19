import math
import time
from collections import defaultdict, deque
from collections.abc import Callable, Hashable


class RateLimiter:
    """Sliding window: at most `limit` events per `window_seconds` for each key (e.g. a user id).

    It lives in memory, so it resets when the server restarts and each worker process has its
    own counter. For several workers you would keep the counters in Redis or the database."""

    def __init__(self, limit: int, window_seconds: int, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self._hits: dict[Hashable, deque[float]] = defaultdict(deque)

    def check(self, key: Hashable) -> tuple[bool, int]:
        """Returns (allowed, seconds_to_wait). An allowed call is counted."""
        now = self.clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False, max(1, math.ceil(self.window - (now - hits[0])))
        hits.append(now)
        return True, 0
