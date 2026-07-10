"""Pure in-memory fixed-window rate limiter."""

from __future__ import annotations

from prooflens.api.ratelimit import RateLimiter


def test_allows_up_to_limit_then_blocks_with_retry_after():
    rl = RateLimiter(limits={"general": 3}, window_seconds=60)
    t = 1000.0
    assert rl.check("k1", "general", now=t)[0] is True   # 1
    assert rl.check("k1", "general", now=t)[0] is True   # 2
    assert rl.check("k1", "general", now=t)[0] is True   # 3
    allowed, retry = rl.check("k1", "general", now=t)     # 4 -> blocked
    assert allowed is False
    assert 0 < retry <= 60


def test_window_resets():
    rl = RateLimiter(limits={"general": 1}, window_seconds=60)
    assert rl.check("k1", "general", now=1000.0)[0] is True
    assert rl.check("k1", "general", now=1000.0)[0] is False
    assert rl.check("k1", "general", now=1061.0)[0] is True  # next window


def test_separate_keys_and_tiers_are_independent():
    rl = RateLimiter(limits={"general": 1, "compute": 1}, window_seconds=60)
    assert rl.check("a", "general", now=1000.0)[0] is True
    assert rl.check("b", "general", now=1000.0)[0] is True   # different key
    assert rl.check("a", "compute", now=1000.0)[0] is True   # different tier


def test_zero_limit_disables_tier():
    rl = RateLimiter(limits={"general": 0}, window_seconds=60)
    for _ in range(100):
        assert rl.check("k", "general", now=1000.0)[0] is True  # 0 == unlimited
