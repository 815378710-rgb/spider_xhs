"""
反爬监控仪表盘路由
- 实时状态面板
- 健康检查手动触发
- a1自动续期状态/手动触发
- 签名成功率
- 频率统计
"""
from fastapi import APIRouter, Depends
from core.deps import get_current_user

router = APIRouter()


@router.get("/status")
async def get_crawl_status(user=Depends(get_current_user)):
    """获取反爬系统完整状态"""
    from utils.rate_limiter import rate_limiter
    from utils.proxy_pool import proxy_pool
    from utils.cookie_manager import CookieManager
    from services.health_checker import health_checker
    from utils.fingerprint import get_fingerprint
    from services.a1_refresher import a1_refresher

    cm = CookieManager()
    fp = get_fingerprint()

    return {
        "success": True,
        "data": {
            "cookie": {
                "has_cookie": cm.load_cookie() is not None,
                "a1": cm.extract_a1() or "",
            },
            "health": health_checker.get_stats(),
            "rate_limiter": rate_limiter.get_stats(),
            "proxy_pool": proxy_pool.get_pool_info(),
            "fingerprint": fp.get_summary(),
            "a1_refresh": a1_refresher.get_status(),
        }
    }


@router.post("/health-check")
async def manual_health_check(user=Depends(get_current_user)):
    """手动触发Cookie健康检查"""
    from services.health_checker import health_checker
    result = await health_checker.check_cookie_health()
    return {"success": True, "data": result}


@router.get("/a1-refresh-status")
async def get_a1_refresh_status(user=Depends(get_current_user)):
    """获取a1自动续期状态"""
    from services.a1_refresher import a1_refresher
    from core.config import settings
    return {
        "success": True,
        "data": {
            **a1_refresher.get_status(),
            "auto_refresh_enabled": settings.get_bool("A1_AUTO_REFRESH", True),
            "refresh_interval": settings.get_int("A1_REFRESH_INTERVAL", 480),
        }
    }


@router.post("/a1-refresh")
async def manual_a1_refresh(user=Depends(get_current_user)):
    """手动触发a1续期"""
    from services.a1_refresher import a1_refresher
    result = await a1_refresher.refresh()
    return {"success": True, "data": result}


@router.get("/tls-status")
async def get_tls_status(user=Depends(get_current_user)):
    """获取TLS指纹模拟状态"""
    from core.config import settings
    try:
        import curl_cffi
        curl_cffi_available = True
        curl_cffi_version = getattr(curl_cffi, '__version__', 'unknown')
    except ImportError:
        curl_cffi_available = False
        curl_cffi_version = ""

    return {
        "success": True,
        "data": {
            "curl_cffi_available": curl_cffi_available,
            "curl_cffi_version": curl_cffi_version,
            "impersonate_target": settings.get("CURL_CFFI_IMPERSONATE", "chrome120"),
            "tls_enabled": settings.get_bool("CURL_CFFI_ENABLED", True),
        }
    }


@router.post("/test-request")
async def test_xhs_request(body: dict, user=Depends(get_current_user)):
    """测试发送XHS请求"""
    api = body.get("api", "/api/sns/web/v1/user/self")
    from utils.xhs_http_client import xhs_client
    result = await xhs_client.get(api)
    return {"success": True, "data": result}
