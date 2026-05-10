"""
反爬配置路由 — 频率控制 / 代理池 / 指纹管理
"""
from fastapi import APIRouter, Depends
from core.deps import get_current_user

router = APIRouter()


@router.get("/config")
async def get_anti_crawl_config(user=Depends(get_current_user)):
    from utils.rate_limiter import rate_limiter
    from utils.proxy_pool import proxy_pool
    fp_info = {}
    try:
        from utils.fingerprint import get_fingerprint
        fp = get_fingerprint()
        fp_info = fp.get_summary()
    except Exception:
        pass
    return {
        "success": True,
        "rate_limiter": rate_limiter.get_stats(),
        "proxy_pool": proxy_pool.get_pool_info(),
        "fingerprint": fp_info,
    }


@router.post("/config")
async def update_anti_crawl_config(body: dict, user=Depends(get_current_user)):
    from utils.rate_limiter import rate_limiter
    from utils.proxy_pool import proxy_pool
    rl = body.get("rate_limiter", {})
    if rl:
        rate_limiter.update_config(
            min_delay=rl.get("min_delay"),
            max_delay=rl.get("max_delay"),
            max_concurrent=rl.get("max_concurrent"),
        )
    pp = body.get("proxy_pool", {})
    if pp:
        proxy_pool.update_config(
            enabled=pp.get("enabled"),
            proxy_list=pp.get("proxies"),
            check_interval=pp.get("check_interval"),
        )
    return {"success": True, "message": "反爬配置已更新"}


@router.post("/fingerprint")
async def regenerate_fingerprint(user=Depends(get_current_user)):
    from utils.fingerprint import regenerate_fingerprint
    fp = regenerate_fingerprint()
    import xhs_utils.xhs_util as xu
    xu._FINGERPRINT_CACHE = None
    return {"success": True, "message": "新指纹已生成", "fingerprint": fp.get_summary()}


@router.post("/proxy/check")
async def check_proxy_health(user=Depends(get_current_user)):
    from utils.proxy_pool import proxy_pool
    results = proxy_pool.health_check()
    return {"success": True, "results": results}
