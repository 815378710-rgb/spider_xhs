# encoding: utf-8
"""
请求频率控制器 — 防止被反爬检测
- 可配置的请求间隔（默认 5-15 秒随机延迟）
- 全局并发限制（单线程串行）
- 请求队列 + 统计
"""
import time
import random
import threading
import collections
from loguru import logger


class RateLimiter:
    """全局请求频率控制器"""

    def __init__(self, min_delay=5.0, max_delay=15.0, max_concurrent=1):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_concurrent = max_concurrent

        self._lock = threading.Lock()
        self._last_request_time = 0.0
        self._active_count = 0
        self._queue = collections.deque()
        self._stats = {
            'total_requests': 0,
            'total_wait_time': 0.0,
            'avg_delay': 0.0,
        }

    def update_config(self, min_delay=None, max_delay=None, max_concurrent=None):
        """动态更新配置"""
        if min_delay is not None:
            self.min_delay = max(0.5, float(min_delay))
        if max_delay is not None:
            self.max_delay = max(self.min_delay + 0.5, float(max_delay))
        if max_concurrent is not None:
            self.max_concurrent = max(1, int(max_concurrent))
        logger.info(f"[rate_limiter] 配置更新: delay={self.min_delay}-{self.max_delay}s, concurrent={self.max_concurrent}")

    def wait_if_needed(self):
        """在发起请求前调用，自动等待必要的延迟"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            # 计算本次需要等待的时间
            delay = random.uniform(self.min_delay, self.max_delay)
            if elapsed < delay:
                wait_time = delay - elapsed
                logger.debug(f"[rate_limiter] 等待 {wait_time:.1f}s (距上次请求 {elapsed:.1f}s)")
                time.sleep(wait_time)
                self._stats['total_wait_time'] += wait_time
            else:
                logger.debug(f"[rate_limiter] 无需等待 (距上次请求 {elapsed:.1f}s)")

            self._last_request_time = time.time()
            self._stats['total_requests'] += 1
            if self._stats['total_requests'] > 0:
                self._stats['avg_delay'] = self._stats['total_wait_time'] / self._stats['total_requests']

    def get_stats(self):
        """返回统计信息"""
        return {
            **self._stats,
            'min_delay': self.min_delay,
            'max_delay': self.max_delay,
            'max_concurrent': self.max_concurrent,
        }

    def reset_stats(self):
        self._stats = {
            'total_requests': 0,
            'total_wait_time': 0.0,
            'avg_delay': 0.0,
        }


# 全局单例
rate_limiter = RateLimiter()
