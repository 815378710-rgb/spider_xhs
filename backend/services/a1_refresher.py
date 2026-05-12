"""
a1 Cookie 自动续期服务
- 每8分钟自动执行续期（a1有效期仅10分钟）
- 通过访问小红书接口触发a1自动刷新
- 失败时从Cookie池自动切换
- 连续失败3次触发告警通知
"""
import asyncio
import time
from datetime import datetime
from loguru import logger


class A1Refresher:
    """a1 Cookie 自动续期管理器"""

    def __init__(self):
        self._last_refresh = None       # 上次续期时间
        self._refresh_count = 0         # 续期成功次数
        self._fail_count = 0            # 连续失败次数
        self._total_attempts = 0        # 总尝试次数
        self._last_error = ""           # 最近一次错误
        self._current_a1 = ""           # 当前a1前16位（用于展示）
        self._is_refreshing = False     # 是否正在续期中

    async def refresh(self):
        """执行一次a1续期"""
        if self._is_refreshing:
            logger.debug("[A1Refresher] 续期正在进行中，跳过")
            return {"success": False, "message": "续期正在进行中"}

        self._is_refreshing = True
        self._total_attempts += 1

        try:
            result = await self._do_refresh()
            if result.get("success"):
                self._refresh_count += 1
                self._fail_count = 0
                self._last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._current_a1 = result.get("a1_preview", "")
                logger.info(f"[A1Refresher] ✅ 续期成功, a1={self._current_a1}")
            else:
                self._fail_count += 1
                self._last_error = result.get("message", "未知错误")
                self._last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.warning(f"[A1Refresher] ❌ 续期失败(连续{self._fail_count}次): {self._last_error}")

                # 连续失败3次，触发告警
                if self._fail_count >= 3:
                    await self._notify_failure()

            return result
        except Exception as e:
            self._fail_count += 1
            self._last_error = str(e)[:100]
            self._last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.error(f"[A1Refresher] 续期异常: {e}")
            return {"success": False, "message": str(e)[:100]}
        finally:
            self._is_refreshing = False

    async def _do_refresh(self) -> dict:
        """核心续期逻辑"""
        import sys
        import os

        # 确保项目路径在 sys.path 中
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        # 1. 加载当前Cookie
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
            return {"success": False, "message": "没有可用的Cookie"}

        # 2. 提取当前a1
        a1_preview = ""
        try:
            a1_preview = cm.extract_a1() or ""
            a1_preview = a1_preview[:16] + "..." if len(a1_preview) > 16 else a1_preview
        except Exception:
            pass

        # 3. 通过访问API触发a1续期（登录态有效时，请求会自动刷新a1）
        try:
            from apis.xhs_pc_apis import XHS_Apis
            xhs = XHS_Apis()
            success, msg, data = xhs.get_user_self_info(cookie_str)

            if success:
                nickname = data.get("data", {}).get("basic_info", {}).get("nickname", "未知")
                return {
                    "success": True,
                    "message": f"续期成功（用户: {nickname}）",
                    "username": nickname,
                    "a1_preview": a1_preview,
                }
            else:
                # Cookie已失效，尝试从Cookie池获取下一个
                logger.info(f"[A1Refresher] 当前Cookie失效，尝试从Cookie池切换...")
                switch_result = await self._try_switch_from_pool()
                if switch_result.get("success"):
                    return switch_result
                return {"success": False, "message": f"Cookie验证失败: {msg}"}
        except Exception as e:
            return {"success": False, "message": f"请求异常: {str(e)[:80]}"}

    async def _try_switch_from_pool(self) -> dict:
        """从Cookie池切换到下一个有效Cookie"""
        try:
            from xhs_utils.xhs_cookie import XhsCookie
            pool = XhsCookie()

            if not pool.pool:
                return {"success": False, "message": "Cookie池为空"}

            # 先验证池中所有Cookie
            best = pool.get_best_cookie()
            if not best:
                return {"success": False, "message": "Cookie池中没有有效Cookie"}

            # 应用最佳Cookie
            from core.config import settings
            settings.update(COOKIES=best)

            # 同时更新到加密存储
            from utils.cookie_manager import CookieManager
            cm = CookieManager()
            cm.save_cookie(best)

            a1 = ""
            try:
                from xhs_utils.cookie_util import trans_cookies
                cookies = trans_cookies(best)
                a1 = cookies.get("a1", "")[:16]
            except Exception:
                pass

            logger.info(f"[A1Refresher] 已从Cookie池切换，新a1={a1}...")
            return {
                "success": True,
                "message": f"已从Cookie池自动切换",
                "a1_preview": f"{a1}..." if a1 else "",
                "switched": True,
            }
        except Exception as e:
            return {"success": False, "message": f"Cookie池切换失败: {str(e)[:80]}"}

    async def _notify_failure(self):
        """连续失败告警通知"""
        try:
            from core.database import async_session
            from models.notification import Notification
            async with async_session() as db:
                noti = Notification(
                    noti_type="error",
                    title="a1自动续期连续失败",
                    message=f"a1续期已连续失败{self._fail_count}次，最后错误: {self._last_error}，请及时检查Cookie状态",
                )
                db.add(noti)
                await db.commit()
                logger.warning("[A1Refresher] 已发送连续失败告警通知")
        except Exception as e:
            logger.warning(f"[A1Refresher] 告警通知发送失败（非致命）: {e}")

    def get_status(self) -> dict:
        """获取续期状态"""
        success_rate = None
        if self._total_attempts > 0:
            success_rate = round(self._refresh_count / self._total_attempts, 4)
        return {
            "last_refresh": self._last_refresh,
            "refresh_count": self._refresh_count,
            "total_attempts": self._total_attempts,
            "consecutive_failures": self._fail_count,
            "success_rate": success_rate,
            "current_a1": self._current_a1,
            "last_error": self._last_error,
            "is_refreshing": self._is_refreshing,
        }


# 全局单例
a1_refresher = A1Refresher()
