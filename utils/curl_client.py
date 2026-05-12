"""
curl_cffi 封装客户端
- 模拟真实浏览器的 TLS 指纹（JA3/JA4）
- 支持 impersonate 参数模拟 Chrome/Firefox/Safari 的 TLS 握手特征
- 与 httpx 接口兼容，可无缝替换
- 降级策略：curl_cffi 不可用时返回 None
"""
import asyncio
from loguru import logger

# 检测 curl_cffi 是否可用
try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    from curl_cffi.requests import Response as CurlResponse
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    CurlAsyncSession = None
    CurlResponse = None
    logger.info("[curl_client] curl_cffi 未安装，TLS指纹模拟不可用。安装: pip install curl_cffi")


class CurlClient:
    """curl_cffi 异步 HTTP 客户端封装"""

    # 支持的 impersonate 目标
    IMPERSONATE_TARGETS = [
        "chrome99", "chrome100", "chrome101", "chrome104", "chrome107",
        "chrome110", "chrome116", "chrome119", "chrome120", "chrome123",
        "chrome124", "chrome131",
        "edge99", "edge101",
        "safari15_3", "safari15_5", "safari17_0", "safari17_2_4",
        "firefox133",
    ]

    def __init__(self, impersonate: str = "chrome120"):
        self._session = None
        self._impersonate = impersonate
        self._initialized = False

    async def _ensure_session(self):
        """确保 curl_cffi session 已初始化"""
        if not CURL_CFFI_AVAILABLE:
            return False
        if self._session is None or self._session._closed:
            try:
                self._session = CurlAsyncSession(impersonate=self._impersonate)
                self._initialized = True
                logger.debug(f"[curl_client] session 已创建, impersonate={self._impersonate}")
                return True
            except Exception as e:
                logger.warning(f"[curl_client] session 创建失败: {e}")
                return False
        return True

    async def request(
        self,
        method: str,
        url: str,
        headers: dict = None,
        cookies: dict = None,
        data: str = None,
        json_body: dict = None,
        proxies: dict = None,
        timeout: float = 30.0,
    ) -> "CurlResponse | None":
        """
        发送请求（使用 curl_cffi TLS 指纹模拟）

        Returns:
            CurlResponse or None（如果 curl_cffi 不可用）
        """
        if not await self._ensure_session():
            return None

        try:
            # 转换代理格式
            proxy_url = None
            if proxies:
                proxy_url = proxies.get("https") or proxies.get("http")

            # 构建请求参数
            kwargs = {
                "method": method,
                "url": url,
                "headers": headers or {},
                "cookies": cookies or {},
                "timeout": timeout,
            }

            if data:
                kwargs["data"] = data
            elif json_body:
                kwargs["json"] = json_body

            if proxy_url:
                kwargs["proxy"] = proxy_url

            response = await self._session.request(**kwargs)
            return response

        except Exception as e:
            logger.error(f"[curl_client] 请求失败: {e}")
            # session 可能损坏，下次重新创建
            self._session = None
            return None

    async def get(self, url: str, **kwargs) -> "CurlResponse | None":
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> "CurlResponse | None":
        return await self.request("POST", url, **kwargs)

    async def close(self):
        """关闭 session"""
        if self._session and not self._session._closed:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    def get_status(self) -> dict:
        """获取客户端状态"""
        return {
            "available": CURL_CFFI_AVAILABLE,
            "impersonate": self._impersonate,
            "initialized": self._initialized,
            "session_active": self._session is not None and not (self._session._closed if self._session else False),
        }


# 便捷函数
def is_curl_cffi_available() -> bool:
    """检查 curl_cffi 是否可用"""
    return CURL_CFFI_AVAILABLE


def get_impersonate_target() -> str:
    """获取当前 impersonate 目标"""
    try:
        from core.config import settings
        return settings.get("CURL_CFFI_IMPERSONATE", "chrome120")
    except Exception:
        return "chrome120"
