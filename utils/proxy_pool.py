# encoding: utf-8
"""
代理池管理模块
- 支持 HTTP / SOCKS5 代理
- 代理轮询 + 健康检查
- 自动切换失效代理
"""
import time
import random
import threading
import requests
from loguru import logger


class ProxyPool:
    """代理池管理器"""

    def __init__(self):
        self._lock = threading.Lock()
        self._proxies = []          # [{"url": "http://user:pass@host:port", "protocol": "http"}, ...]
        self._index = 0
        self._health = {}           # url -> {"ok": bool, "last_check": float, "fail_count": int}
        self._enabled = False
        self._check_interval = 300  # 5分钟检查一次
        self._timeout = 5

    def update_config(self, enabled=None, proxy_list=None, check_interval=None):
        """更新配置"""
        with self._lock:
            if enabled is not None:
                self._enabled = enabled
            if proxy_list is not None:
                self._proxies = self._parse_proxy_list(proxy_list)
                self._index = 0
                # 初始化健康状态
                for p in self._proxies:
                    if p['url'] not in self._health:
                        self._health[p['url']] = {'ok': True, 'last_check': 0, 'fail_count': 0}
            if check_interval is not None:
                self._check_interval = max(60, int(check_interval))
        logger.info(f"[proxy_pool] 配置更新: enabled={self._enabled}, proxies={len(self._proxies)}")

    def _parse_proxy_list(self, raw_list):
        """解析代理列表
        支持格式:
        - http://host:port
        - http://user:pass@host:port
        - socks5://host:port
        - host:port  (默认HTTP)
        """
        result = []
        if isinstance(raw_list, str):
            raw_list = [line.strip() for line in raw_list.strip().split('\n') if line.strip()]

        for line in raw_list:
            if not line or line.startswith('#'):
                continue
            line = line.strip()
            if line.startswith('http://') or line.startswith('https://'):
                protocol = 'http'
            elif line.startswith('socks5://'):
                protocol = 'socks5'
            else:
                protocol = 'http'
                if not line.startswith('http'):
                    line = 'http://' + line
            result.append({'url': line, 'protocol': protocol})

        return result

    def get_proxy(self):
        """获取下一个可用代理，返回 requests 格式的 proxies dict 或 None"""
        with self._lock:
            if not self._enabled or not self._proxies:
                return None

            # 轮询 + 跳过不健康的
            attempts = len(self._proxies)
            for _ in range(attempts):
                idx = self._index % len(self._proxies)
                self._index += 1
                proxy = self._proxies[idx]
                health = self._health.get(proxy['url'], {})
                if health.get('ok', True):
                    return {
                        'http': proxy['url'],
                        'https': proxy['url'],
                    }
                # 如果失败次数太多，跳过
                if health.get('fail_count', 0) >= 3:
                    logger.debug(f"[proxy_pool] 跳过不健康代理: {proxy['url'][:40]}...")
                    continue

            # 所有代理都不健康，返回 None（让直连兜底）
            logger.warning("[proxy_pool] 所有代理不健康，使用直连")
            return None

    def report_success(self, proxy_url):
        """报告代理请求成功"""
        with self._lock:
            if proxy_url in self._health:
                self._health[proxy_url]['ok'] = True
                self._health[proxy_url]['fail_count'] = 0
                self._health[proxy_url]['last_check'] = time.time()

    def report_failure(self, proxy_url):
        """报告代理请求失败"""
        with self._lock:
            if proxy_url in self._health:
                self._health[proxy_url]['fail_count'] += 1
                if self._health[proxy_url]['fail_count'] >= 3:
                    self._health[proxy_url]['ok'] = False
                    logger.warning(f"[proxy_pool] 标记代理为不健康: {proxy_url[:40]}... "
                                   f"(连续失败 {self._health[proxy_url]['fail_count']} 次)")

    def health_check(self):
        """对所有代理做健康检查"""
        with self._lock:
            proxies_to_check = list(self._proxies)

        results = []
        for proxy in proxies_to_check:
            ok = self._check_single(proxy)
            with self._lock:
                self._health[proxy['url']] = {
                    'ok': ok,
                    'last_check': time.time(),
                    'fail_count': 0 if ok else self._health.get(proxy['url'], {}).get('fail_count', 0) + 1,
                }
            results.append({'url': proxy['url'][:40], 'ok': ok})

        logger.info(f"[proxy_pool] 健康检查完成: {sum(1 for r in results if r['ok'])}/{len(results)} 可用")
        return results

    def _check_single(self, proxy):
        """检查单个代理是否可用"""
        proxies = {'http': proxy['url'], 'https': proxy['url']}
        try:
            resp = requests.request(
                'GET', 'http://httpbin.org/ip',
                proxies=proxies,
                timeout=self._timeout,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"[proxy_pool] 代理检查失败 {proxy['url'][:30]}...: {e}")
            return False

    def get_pool_info(self):
        """返回代理池状态信息"""
        with self._lock:
            healthy = sum(1 for h in self._health.values() if h.get('ok', True))
            total = len(self._proxies)
            return {
                'enabled': self._enabled,
                'total': total,
                'healthy': healthy,
                'unhealthy': total - healthy,
                'proxies': [
                    {
                        'url': p['url'][:40] + '...',
                        'protocol': p['protocol'],
                        'ok': self._health.get(p['url'], {}).get('ok', True),
                        'fail_count': self._health.get(p['url'], {}).get('fail_count', 0),
                    }
                    for p in self._proxies
                ],
            }


# 全局单例
proxy_pool = ProxyPool()
