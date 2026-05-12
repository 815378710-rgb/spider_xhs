"""
小红书统一HTTP客户端
集成：签名自动注入 + 频率控制 + 代理 + 重试 + 响应验证
所有XHS API请求都应通过此客户端发起
"""
import httpx
import asyncio
import time
import random
from loguru import logger


class XHSHttpClient:
    """小红书统一HTTP客户端"""

    BASE_URL = "https://edith.xiaohongshu.com"
    WEB_URL = "https://www.xiaohongshu.com"

    def __init__(self):
        self._client = None  # httpx.AsyncClient, lazy init

    def _get_rate_limiter(self):
        from utils.rate_limiter import rate_limiter
        return rate_limiter

    def _get_proxy_pool(self):
        from utils.proxy_pool import proxy_pool
        return proxy_pool

    def _get_fingerprint(self):
        from utils.fingerprint import get_fingerprint
        return get_fingerprint()

    def _get_cookie_manager(self):
        from utils.cookie_manager import CookieManager
        return CookieManager()

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建httpx客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self._client

    async def request(
        self,
        method: str,
        api: str,
        data: dict = None,
        cookie_name: str = "default",
        max_retries: int = 3,
        retry_delay: float = 5.0,
        use_proxy: bool = False,
    ) -> dict:
        """
        发送签名请求

        Returns:
            {
                "success": bool,
                "status_code": int,
                "data": dict | None,
                "error": str,
                "trace_id": str,
            }
        """
        rate_limiter = self._get_rate_limiter()
        proxy_pool = self._get_proxy_pool()
        fingerprint = self._get_fingerprint()
        cookie_manager = self._get_cookie_manager()

        # 1. 频率控制等待
        try:
            await rate_limiter.wait_if_needed_async(api)
        except Exception as e:
            logger.warning(f"[XHSHttpClient] 频率控制异常，继续请求: {e}")

        # 2. 获取Cookie
        cookie_str = cookie_manager.load_cookie(cookie_name)
        if not cookie_str:
            # 降级到settings
            try:
                from core.config import settings
                cookie_str = settings.COOKIES
            except Exception:
                pass
        if not cookie_str:
            return {"success": False, "status_code": 0, "data": None,
                    "error": "Cookie未配置", "trace_id": ""}

        # 3. 生成签名头
        try:
            from xhs_utils.xhs_util import generate_request_params
            headers, cookies, body = generate_request_params(cookie_str, api, data or '', method)
        except Exception as e:
            logger.error(f"[XHSHttpClient] 签名生成失败: {e}")
            return {"success": False, "status_code": 0, "data": None,
                    "error": f"签名失败: {str(e)[:80]}", "trace_id": ""}

        trace_id = headers.get("x-b3-traceid", "")

        # 4. 获取代理
        proxies = None
        if use_proxy:
            proxies = proxy_pool.get_proxy()

        # 5. 重试循环
        last_error = ""
        for attempt in range(max_retries):
            try:
                client = await self._get_client()
                response = await client.request(
                    method=method,
                    url=f"{self.BASE_URL}{api}",
                    headers=headers,
                    cookies=cookies,
                    content=body if body else None,
                    proxies=proxies,
                )

                # 6. 响应验证
                result = self._validate_response(response)
                result["trace_id"] = trace_id

                if result["success"]:
                    if proxies:
                        proxy_pool.report_success(proxies.get("http", ""))
                    return result
                else:
                    status = response.status_code
                    if status == 461:
                        logger.warning(f"[XHSHttpClient] 反爬拦截 (461), trace={trace_id}")
                        return result
                    if status == 403:
                        logger.warning("[XHSHttpClient] 403 Forbidden, Cookie可能已过期")
                        result["cookie_expired"] = True
                        return result
                    last_error = result.get("error", f"HTTP {status}")

            except httpx.TimeoutException:
                last_error = f"请求超时"
                logger.warning(f"[XHSHttpClient] 请求超时 ({attempt+1}/{max_retries}): {api}")
            except httpx.ConnectError as e:
                last_error = f"连接失败: {str(e)[:50]}"
                logger.warning(f"[XHSHttpClient] 连接失败 ({attempt+1}/{max_retries}): {api}")
                if proxies:
                    proxy_pool.report_failure(proxies.get("http", ""))
                    proxies = proxy_pool.get_proxy()
            except Exception as e:
                last_error = str(e)[:80]
                logger.error(f"[XHSHttpClient] 请求异常 ({attempt+1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                wait = retry_delay * (attempt + 1) + random.uniform(0, 2)
                await asyncio.sleep(wait)

        return {"success": False, "status_code": 0, "data": None,
                "error": f"重试{max_retries}次后仍失败: {last_error}", "trace_id": trace_id}

    def _validate_response(self, response) -> dict:
        """多层验证响应"""
        try:
            from utils.fetch_validator import validate_fetch_result
            return validate_fetch_result(response)
        except Exception as e:
            # 简单兜底验证
            try:
                data = response.json()
                return {
                    "success": response.status_code == 200 and data.get("code", -1) == 0,
                    "status_code": response.status_code,
                    "data": data,
                    "error": "" if response.status_code == 200 else f"HTTP {response.status_code}",
                    "cookie_expired": False,
                    "completeness": 0,
                    "checks": {},
                }
            except Exception:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "data": None,
                    "error": f"响应验证失败: {e}",
                    "cookie_expired": False,
                    "completeness": 0,
                    "checks": {},
                }

    async def get(self, api: str, **kwargs) -> dict:
        return await self.request("GET", api, **kwargs)

    async def post(self, api: str, data: dict = None, **kwargs) -> dict:
        return await self.request("POST", api, data=data, **kwargs)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# 全局单例
xhs_client = XHSHttpClient()
