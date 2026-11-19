from app.services.rate_limit import RateLimiter


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_blocks_after_the_limit_and_says_how_long_to_wait():
    clock = Clock()
    limiter = RateLimiter(limit=3, window_seconds=3600, clock=clock)
    for _ in range(3):
        assert limiter.check(1) == (True, 0)
        clock.now += 10
    allowed, retry_after = limiter.check(1)
    assert allowed is False
    assert retry_after == 3600 - 30  

def test_the_window_slides():
    clock = Clock()
    limiter = RateLimiter(limit=2, window_seconds=100, clock=clock)
    limiter.check(1)
    clock.now += 60
    limiter.check(1)
    assert limiter.check(1)[0] is False
    clock.now += 41  
    assert limiter.check(1)[0] is True


def test_each_user_has_their_own_counter():
    limiter = RateLimiter(limit=1, window_seconds=3600, clock=Clock())
    assert limiter.check(1)[0] is True
    assert limiter.check(1)[0] is False
    assert limiter.check(2)[0] is True


def test_a_blocked_attempt_is_not_counted():
    clock = Clock()
    limiter = RateLimiter(limit=1, window_seconds=100, clock=clock)
    limiter.check(1)
    for _ in range(5):
        assert limiter.check(1)[0] is False  
    clock.now += 100
    assert limiter.check(1)[0] is True
