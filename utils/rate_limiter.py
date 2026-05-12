# encoding: utf-8
"""
请求频率控制器 — 防止被反爬检测
升级版：
- 正态分布延时（替代均匀分布）
- 每分钟请求数限制
- 每日请求数限制
- 同接口连续请求暂停
- 智能批量延时
- 异步版本
"""
import time
import random
import asyncio
import threading
import collections
from datetime import datetime, date
from loguru import logger


class RateLimiter:
    """全局请求频率控制器（智能版）"""

    def __init__(self, min_delay=5.0, max_delay=15.0, max_concurrent=1):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_concurrent = max_concurrent

        self._lock = threading.Lock()
        self._last_request_time = 0.0
        self._active_count = 0
        self._queue = collections.deque()

        # 正态分布参数
        self._normal_mean = 5.0
        self._normal_std = 1.5
        self._delay_min = 2.0
        self._delay_max = 10.0

        # 每分钟限制
        self._minute_requests = []  # timestamp list
        self.MAX_PER_MINUTE = 5

        # 每日限制
        self._daily_count = 0
        self._daily_date = None
        self.MAX_PER_DAY = 100

        # 同接口连续请求
        self._consecutive_count = 0
        self._last_api = None
        self.MAX_CONSECUTIVE = 10
        self.PAUSE_AFTER_CONSECUTIVE = 30  # 秒

        self._stats = {
            'total_requests': 0,
            'total_wait_time': 0.0,
            'avg_delay': 0.0,
        }

    def _normal_delay(self) -> float:
        """正态分布延时：均值5秒，标准差1.5秒，限制2-10秒"""
        delay = random.gauss(self._normal_mean, self._normal_std)
        return max(self._delay_min, min(delay, self._delay_max))

    def _clean_minute_requests(self):
        """清理过期的分钟请求记录"""
        now = time.time()
        self._minute_requests = [t for t in self._minute_requests if now - t < 60]

    def _check_minute_limit(self) -> float:
        """检查每分钟限制，返回需要等待的秒数"""
        self._clean_minute_requests()
        if len(self._minute_requests) >= self.MAX_PER_MINUTE:
            oldest = self._minute_requests[0]
            wait = 60 - (time.time() - oldest)
            if wait > 0:
                return wait
        return 0

    def _check_daily_limit(self) -> bool:
        """检查每日限制，返回True表示已达上限"""
        today = date.today()
        if self._daily_date != today:
            self._daily_date = today
            self._daily_count = 0
        return self._daily_count >= self.MAX_PER_DAY

    def _check_consecutive(self, api: str) -> float:
        """检查同接口连续请求，返回需要暂停的秒数"""
        if api == self._last_api:
            self._consecutive_count += 1
            if self._consecutive_count >= self.MAX_CONSECUTIVE:
                self._consecutive_count = 0
                return self.PAUSE_AFTER_CONSECUTIVE
        else:
            self._consecutive_count = 1
            self._last_api = api
        return 0

    def update_config(self, min_delay=None, max_delay=None, max_concurrent=None):
        """动态更新配置"""
        if min_delay is not None:
            self.min_delay = max(0.5, float(min_delay))
        if max_delay is not None:
            self.max_delay = max(self.min_delay + 0.5, float(max_delay))
        if max_concurrent is not None:
            self.max_concurrent = max(1, int(max_concurrent))
        logger.info(f"[rate_limiter] 配置更新: delay={self.min_delay}-{self.max_delay}s, concurrent={self.max_concurrent}")

    def wait_if_needed(self, api: str = ""):
        """在发起请求前调用，自动等待必要的延迟（同步版）"""
        with self._lock:
            # 检查每日限制
            if self._check_daily_limit():
                logger.warning("[rate_limiter] 已达每日请求上限，暂停")
                time.sleep(60)
                return

            # 检查同接口连续暂停
            pause = self._check_consecutive(api)
            if pause > 0:
                logger.info(f"[rate_limiter] 同接口连续请求过多，暂停 {pause}s")
                time.sleep(pause)

            # 检查每分钟限制
            minute_wait = self._check_minute_limit()
            if minute_wait > 0:
                logger.info(f"[rate_limiter] 每分钟限制，等待 {minute_wait:.1f}s")
                time.sleep(minute_wait)

            # 正态分布延时
            now = time.time()
            elapsed = now - self._last_request_time
            delay = self._normal_delay()
            if elapsed < delay:
                wait_time = delay - elapsed
                logger.debug(f"[rate_limiter] 等待 {wait_time:.1f}s (距上次请求 {elapsed:.1f}s)")
                time.sleep(wait_time)
                self._stats['total_wait_time'] += wait_time
            else:
                logger.debug(f"[rate_limiter] 无需等待 (距上次请求 {elapsed:.1f}s)")

            self._last_request_time = time.time()
            self._minute_requests.append(time.time())
            self._daily_count += 1
            self._stats['total_requests'] += 1
            if self._stats['total_requests'] > 0:
                self._stats['avg_delay'] = self._stats['total_wait_time'] / self._stats['total_requests']

    async def wait_if_needed_async(self, api: str = ""):
        """异步版本的频率控制"""
        with self._lock:
            # 检查每日限制
            if self._check_daily_limit():
                logger.warning("[rate_limiter] 已达每日请求上限，暂停")
                await asyncio.sleep(60)
                return

            # 检查同接口连续暂停
            pause = self._check_consecutive(api)
            if pause > 0:
                logger.info(f"[rate_limiter] 同接口连续请求过多，暂停 {pause}s")
                await asyncio.sleep(pause)

            # 检查每分钟限制
            minute_wait = self._check_minute_limit()
            if minute_wait > 0:
                logger.info(f"[rate_limiter] 每分钟限制，等待 {minute_wait:.1f}s")
                await asyncio.sleep(minute_wait)

            # 正态分布延时
            now = time.time()
            elapsed = now - self._last_request_time
            delay = self._normal_delay()
            if elapsed < delay:
                wait_time = delay - elapsed
                logger.debug(f"[rate_limiter] 等待 {wait_time:.1f}s (距上次请求 {elapsed:.1f}s)")
                await asyncio.sleep(wait_time)
                self._stats['total_wait_time'] += wait_time
            else:
                logger.debug(f"[rate_limiter] 无需等待 (距上次请求 {elapsed:.1f}s)")

            self._last_request_time = time.time()
            self._minute_requests.append(time.time())
            self._daily_count += 1
            self._stats['total_requests'] += 1
            if self._stats['total_requests'] > 0:
                self._stats['avg_delay'] = self._stats['total_wait_time'] / self._stats['total_requests']

    def batch_delay(self, count: int):
        """智能批量延时：每15条请求额外暂停30-60秒"""
        if count > 0 and count % 15 == 0:
            pause = random.uniform(30, 60)
            logger.info(f"[rate_limiter] 批量延时: 第{count}条，暂停 {pause:.1f}s")
            time.sleep(pause)

    def get_stats(self):
        """返回所有统计维度"""
        with self._lock:
            self._clean_minute_requests()
            return {
                **self._stats,
                'min_delay': self.min_delay,
                'max_delay': self.max_delay,
                'max_concurrent': self.max_concurrent,
                'minute_requests': len(self._minute_requests),
                'max_per_minute': self.MAX_PER_MINUTE,
                'daily_count': self._daily_count,
                'max_per_day': self.MAX_PER_DAY,
                'daily_date': str(self._daily_date),
                'consecutive_count': self._consecutive_count,
                'max_consecutive': self.MAX_CONSECUTIVE,
            }

    def reset_stats(self):
        self._stats = {
            'total_requests': 0,
            'total_wait_time': 0.0,
            'avg_delay': 0.0,
        }


# 全局单例
rate_limiter = RateLimiter()
