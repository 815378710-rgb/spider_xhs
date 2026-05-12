"""
Cookie健康巡检服务
- 每2小时自动检查Cookie有效性
- 检测到过期时通知用户
- 签名成功率监控
"""
import asyncio
from loguru import logger


class HealthChecker:
    def __init__(self):
        self._last_check = None
        self._check_count = 0
        self._failure_count = 0
        self._sign_success_count = 0
        self._sign_fail_count = 0

    async def check_cookie_health(self):
        """健康巡检主函数"""
        try:
            from utils.cookie_manager import CookieManager
            cm = CookieManager()

            cookie_str = cm.load_cookie()
            if not cookie_str:
                # 降级到settings
                try:
                    from core.config import settings
                    cookie_str = settings.COOKIES
                except Exception:
                    pass

            if not cookie_str:
                logger.warning("[HealthChecker] 没有存储的Cookie")
                result = {"status": "no_cookie", "message": "未配置Cookie", "valid": False}
                self._last_check = result
                self._check_count += 1
                return result

            check_result = cm.health_check(cookie_str)
            self._last_check = check_result
            self._check_count += 1

            if not check_result.get("valid"):
                self._failure_count += 1
                logger.warning(f"[HealthChecker] Cookie已过期: {check_result.get('error')}")
                await self._notify_cookie_expired(check_result)
            else:
                self._failure_count = 0
                logger.info(f"[HealthChecker] Cookie有效, 用户: {check_result.get('username')}")

            check_result["status"] = "ok" if check_result.get("valid") else "expired"
            return check_result
        except Exception as e:
            logger.error(f"[HealthChecker] 健康检查异常: {e}")
            return {"status": "error", "message": str(e), "valid": False}

    async def _notify_cookie_expired(self, result: dict):
        """通过通知系统发送Cookie过期告警"""
        try:
            from core.database import async_session
            from models.notification import Notification
            async with async_session() as db:
                noti = Notification(
                    noti_type="warning",
                    title="Cookie已过期",
                    message=f"Cookie验证失败: {result.get('error', '未知错误')}，请及时更新",
                )
                db.add(noti)
                await db.commit()
        except Exception as e:
            logger.warning(f"[HealthChecker] 通知发送失败（非致命）: {e}")

    def record_sign_attempt(self, success: bool):
        """记录签名尝试结果"""
        if success:
            self._sign_success_count += 1
        else:
            self._sign_fail_count += 1

    def get_stats(self) -> dict:
        total = self._sign_success_count + self._sign_fail_count
        return {
            "last_check": self._last_check,
            "check_count": self._check_count,
            "consecutive_failures": self._failure_count,
            "sign_success_rate": round(self._sign_success_count / total, 4) if total > 0 else None,
            "sign_total": total,
        }


# 全局单例
health_checker = HealthChecker()
