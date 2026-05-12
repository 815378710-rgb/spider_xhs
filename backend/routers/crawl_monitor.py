"""
反爬监控仪表盘路由
- 实时状态面板
- 健康检查手动触发
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
        }
    }


@router.post("/health-check")
async def manual_health_check(user=Depends(get_current_user)):
    """手动触发Cookie健康检查"""
    from services.health_checker import health_checker
    result = await health_checker.check_cookie_health()
    return {"success": True, "data": result}


@router.post("/test-request")
async def test_xhs_request(body: dict, user=Depends(get_current_user)):
    """测试发送XHS请求"""
    api = body.get("api", "/api/sns/web/v1/user/self")
    from utils.xhs_http_client import xhs_client
    result = await xhs_client.get(api)
    return {"success": True, "data": result}
