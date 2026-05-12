"""
小红书统一HTTP客户端
集成：签名自动注入 + 频率控制 + 代理 + 重试 + 响应验证 + TLS指纹模拟(curl_cffi)
所有XHS API请求都应通过此客户端发起
"""
import httpx
import asyncio
import time
import random
from loguru import logger

# 检测 curl_cffi 可用性
try:
    from utils.curl_client import CurlClient, CURL_CFFI_AVAILABLE
except ImportError:
    CURL_CFFI_AVAILABLE = False
    CurlClient = None


class XHSHttpClient:
    """小红书统一HTTP客户端"""

    BASE_URL = "https://edith.xiaohongshu.com"
    WEB_URL = "https://www.xiaohongshu.com"

    def __init__(self):
        self._httpx_client = None  # httpx.AsyncClient, lazy init
        self._curl_client = None   # CurlClient, lazy init
        self._use_curl = False     # 是否使用 curl_cffi

    def _init_tls_client(self):
        """初始化TLS指纹模拟客户端"""
        try:
            from core.config import settings
            if settings.get_bool("CURL_CFFI_ENABLED", True) and CURL_CFFI_AVAILABLE and CurlClient:
                impersonate = settings.get("CURL_CFFI_IMPERSONATE", "chrome120")
                self._curl_client = CurlClient(impersonate=impersonate)
                self._use_curl = True
                logger.info(f"[XHSHttpClient] 使用 curl_cffi TLS指纹模拟 (impersonate={impersonate})")
                return
        except Exception as e:
            logger.debug(f"[XHSHttpClient] curl_cffi初始化跳过: {e}")

        self._use_curl = False
        logger.info("[XHSHttpClient] 使用 httpx 标准请求（无TLS指纹模拟）")

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

    async def _get_httpx_client(self) -> httpx.AsyncClient:
        """获取或创建httpx客户端（降级方案）"""
        if self._httpx_client is None or self._httpx_client.is_closed:
            self._httpx_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self._httpx_client

    async def _get_curl_client(self):
        """获取或创建curl_cffi客户端"""
        if self._curl_client is None:
            self._init_tls_client()
        return self._curl_client

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
        发送签名请求（优先使用curl_cffi TLS指纹模拟）

        Returns:
            {
                "success": bool,
                "status_code": int,
                "data": dict | None,
                "error": str,
                "trace_id": str,
                "tls_client": str,  # "curl_cffi" or "httpx"
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
                    "error": "Cookie未配置", "trace_id": "", "tls_client": "none"}

        # 3. 生成签名头
        try:
            from xhs_utils.xhs_util import generate_request_params
            headers, cookies, body = generate_request_params(cookie_str, api, data or '', method)
        except Exception as e:
            logger.error(f"[XHSHttpClient] 签名生成失败: {e}")
            return {"success": False, "status_code": 0, "data": None,
                    "error": f"签名失败: {str(e)[:80]}", "trace_id": "", "tls_client": "none"}

        trace_id = headers.get("x-b3-traceid", "")

        # 4. 获取代理
        proxies = None
        if use_proxy:
            proxies = proxy_pool.get_proxy()

        # 5. 确定TLS客户端
        use_curl = self._use_curl
        tls_client_name = "curl_cffi" if use_curl else "httpx"

        # 6. 重试循环
        last_error = ""
        for attempt in range(max_retries):
            try:
                if use_curl:
                    # ── curl_cffi 路径（TLS指纹模拟） ──
                    curl = await self._get_curl_client()
                    if curl is None:
                        use_curl = False
                        tls_client_name = "httpx"
                        raise Exception("curl_cffi不可用，切换到httpx")

                    response = await curl.request(
                        method=method,
                        url=f"{self.BASE_URL}{api}",
                        headers=headers,
                        cookies=cookies,
                        data=body if body else None,
                        proxies=proxies,
                    )
                    if response is None:
                        # curl_cffi 请求失败，降级到 httpx
                        use_curl = False
                        tls_client_name = "httpx"
                        logger.warning("[XHSHttpClient] curl_cffi请求失败，降级到httpx")
                        raise Exception("curl_cffi响应为空")

                    # 将 curl_cffi 响应适配为统一格式
                    result = self._validate_curl_response(response)
                    result["trace_id"] = trace_id
                    result["tls_client"] = "curl_cffi"

                else:
                    # ── httpx 路径（标准请求） ──
                    client = await self._get_httpx_client()
                    response = await client.request(
                        method=method,
                        url=f"{self.BASE_URL}{api}",
                        headers=headers,
                        cookies=cookies,
                        content=body if body else None,
                        proxies=proxies,
                    )
                    result = self._validate_response(response)
                    result["trace_id"] = trace_id
                    result["tls_client"] = "httpx"

                # 7. 响应判断
                if result["success"]:
                    if proxies:
                        proxy_pool.report_success(proxies.get("http", ""))
                    return result
                else:
                    status = result.get("status_code", 0)
                    if status == 461:
                        logger.warning(f"[XHSHttpClient] 反爬拦截 (461), trace={trace_id}, tls={tls_client_name}")
                        return result
                    if status == 403:
                        logger.warning("[XHSHttpClient] 403 Forbidden, Cookie可能已过期")
                        result["cookie_expired"] = True
                        return result
                    last_error = result.get("error", f"HTTP {status}")

            except (httpx.TimeoutException,) if not use_curl else Exception:
                last_error = "请求超时"
                logger.warning(f"[XHSHttpClient] 请求超时 ({attempt+1}/{max_retries}): {api}")
            except (httpx.ConnectError,) if not use_curl else Exception:
                last_error = "连接失败"
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
                "error": f"重试{max_retries}次后仍失败: {last_error}",
                "trace_id": trace_id, "tls_client": tls_client_name}

    def _validate_curl_response(self, response) -> dict:
        """验证 curl_cffi 响应"""
        try:
            status_code = response.status_code
            try:
                data = response.json()
            except Exception:
                data = None

            if data is not None:
                return {
                    "success": status_code == 200 and data.get("code", -1) == 0,
                    "status_code": status_code,
                    "data": data,
                    "error": "" if status_code == 200 else f"HTTP {status_code}",
                    "cookie_expired": False,
                    "completeness": 0,
                    "checks": {},
                }
            else:
                return {
                    "success": False,
                    "status_code": status_code,
                    "data": None,
                    "error": f"响应解析失败 (HTTP {status_code})",
                    "cookie_expired": False,
                    "completeness": 0,
                    "checks": {},
                }
        except Exception as e:
            return {
                "success": False,
                "status_code": 0,
                "data": None,
                "error": f"curl_cffi响应验证异常: {e}",
                "cookie_expired": False,
                "completeness": 0,
                "checks": {},
            }

    def _validate_response(self, response) -> dict:
        """多层验证响应（httpx路径）"""
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
        if self._httpx_client and not self._httpx_client.is_closed:
            await self._httpx_client.aclose()
        if self._curl_client:
            await self._curl_client.close()


# 全局单例
xhs_client = XHSHttpClient()
