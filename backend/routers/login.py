"""
登录路由 — 浏览器扫码登录 + 手机登录
"""
import time
import asyncio
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user
from loguru import logger

router = APIRouter()

# In-memory login sessions (same as original Flask app)
LOGIN_SESSIONS = {}
LOGIN_SESSION_TTL = 300


# ═══════════════════════════════════════════════════════════════════════════════
#  浏览器扫码登录 (Playwright)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/browser/start")
async def browser_login_start(user=Depends(get_current_user)):
    """Start a browser-based QR login session using Playwright."""
    try:
        from services.browser_login import create_browser_session, cleanup_old_sessions
        cleanup_old_sessions()
        session = create_browser_session()
        # P0-4 修复：使用await asyncio.sleep代替time.sleep，避免阻塞事件循环
        await asyncio.sleep(3)
        status = session.get_status()
        return {
            "success": True,
            "session_id": session.session_id,
            "status": status["status"],
            "qr_image_b64": status["qr_image_b64"],
            "qr_url": status["qr_url"],
        }
    except ImportError:
        return {"success": False, "message": "浏览器登录组件未安装（需要playwright + chromium）"}
    except Exception as e:
        logger.exception(f"启动浏览器登录异常: {e}")
        return {"success": False, "message": f"启动浏览器异常: {str(e)[:100]}"}


@router.post("/browser/check")
async def browser_login_check(body: dict, user=Depends(get_current_user)):
    """Check browser login session status and save cookies on success."""
    session_id = body.get("session_id", "")
    try:
        from services.browser_login import get_browser_session
        session = get_browser_session(session_id)
        if not session:
            return {"success": False, "message": "登录会话不存在或已过期"}

        status = session.get_status()

        if status["status"] == "completed" and status["cookies_str"]:
            # Save cookies
            settings.update(COOKIES=status["cookies_str"])
            logger.info(f"[browser_login] Cookie saved! length={len(status['cookies_str'])}")

            # Try to get user info
            nickname = "未知"
            try:
                from apis.xhs_pc_apis import XHS_Apis
                ok, msg, data = XHS_Apis().get_user_self_info(status["cookies_str"])
                if ok and data:
                    nickname = data.get("nickname", "未知")
            except:
                pass

            return {
                "success": True,
                "message": f"登录成功！用户: {nickname}",
                "cookies": status["cookies_str"],
            }
        elif status["status"] == "secondary_verify":
            # 二次验证信息
            return {
                "success": False,
                "status": "secondary_verify",
                "message": status.get("verification_data", {}).get("message", "需要完成验证"),
                "verification_type": status.get("verification_type"),
                "verification_data": status.get("verification_data"),
                "verification_screenshot_b64": status.get("verification_screenshot_b64"),
            }
        elif status["status"] == "failed":
            return {"success": False, "message": status.get("error_message", "登录失败")}
        else:
            # Still waiting
            return {
                "success": False,
                "message": "请扫描二维码..." if status["status"] == "scanning" else "正在加载...",
                "status": status["status"],
                "qr_image_b64": status["qr_image_b64"],
                "qr_url": status["qr_url"],
                "elapsed": status["elapsed"],
            }
    except Exception as e:
        logger.exception(f"检查浏览器登录状态异常: {e}")
        return {"success": False, "message": f"检查状态异常: {str(e)[:80]}"}


@router.post("/browser/stop")
async def browser_login_stop(body: dict, user=Depends(get_current_user)):
    """Stop a browser login session."""
    session_id = body.get("session_id", "")
    try:
        from services.browser_login import get_browser_session
        session = get_browser_session(session_id)
        if session:
            session.stop()
        return {"success": True, "message": "已停止"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/browser/verify")
async def browser_login_verify(body: dict, user=Depends(get_current_user)):
    """提交二次验证结果（验证码/确认扫码等）"""
    session_id = body.get("session_id", "")
    verification_type = body.get("type", "")  # "phone_sms" | "captcha" | "device_qr" | "refresh"
    code = body.get("code", "")

    try:
        from services.browser_login import get_browser_session
        session = get_browser_session(session_id)
        if not session:
            return {"success": False, "message": "登录会话不存在或已过期"}

        ok = session.submit_verification(verification_type, code)
        msg = "验证结果已提交，正在处理..." if verification_type != "refresh" else "已刷新"
        return {"success": True, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _cleanup_login_sessions():
    now = time.time()
    expired = [sid for sid, s in LOGIN_SESSIONS.items() if now - s.get("created_at", 0) > LOGIN_SESSION_TTL]
    for sid in expired:
        LOGIN_SESSIONS.pop(sid, None)


@router.post("/qrcode")
async def login_qrcode(user=Depends(get_current_user)):
    """Generate QR code for XHS login."""
    try:
        _cleanup_login_sessions()
        from apis.xhs_pc_login_apis import XHSLoginApi
        login_api = XHSLoginApi()

        try:
            cookies = login_api.generate_init_cookies()
            logger.info(f"[login] init cookies OK, a1={cookies.get('a1', '')[:16]}...")
        except Exception as e:
            return {"success": False, "message": f"生成初始 Cookie 失败: {str(e)[:80]}"}

        try:
            success, msg, qr_data = login_api.generate_qrcode(cookies)
        except Exception as e:
            return {"success": False, "message": f"获取二维码失败: {str(e)[:80]}"}

        if not success:
            return {"success": False, "message": f"获取二维码失败: {msg}"}

        session_id = f"login_{int(time.time() * 1000)}"
        LOGIN_SESSIONS[session_id] = {
            "cookies": qr_data["cookies"],
            "qr_id": qr_data["qr_id"],
            "code": qr_data["code"],
            "qr_url": qr_data["qr_url"],
            "login_api": login_api,
            "created_at": time.time(),
        }

        return {"success": True, "session_id": session_id, "qr_url": qr_data["qr_url"]}
    except Exception as e:
        logger.exception(f"获取二维码异常: {e}")
        return {"success": False, "message": f"服务器异常: {str(e)[:100]}"}


@router.get("/qrcode/status")
async def login_qrcode_status(user=Depends(get_current_user)):
    """Get QR code login session status."""
    return {"success": True, "active_sessions": len(LOGIN_SESSIONS)}


@router.post("/check")
async def login_check(body: dict, user=Depends(get_current_user)):
    """Poll QR code scan status."""
    session_id = body.get("session_id", "")
    session = LOGIN_SESSIONS.get(session_id)
    if not session:
        return {"success": False, "message": "登录会话不存在或已过期"}
    if time.time() - session["created_at"] > 300:
        LOGIN_SESSIONS.pop(session_id, None)
        return {"success": False, "message": "二维码已过期，请重新获取"}

    try:
        login_api = session["login_api"]
        cookies = session["cookies"]

        # Check if already processing a successful scan (prevent duplicate processing)
        if session.get("processing"):
            return {"success": False, "message": "请确认登录"}
        if session.get("completed"):
            return {"success": True, "message": session.get("result_message", "登录成功！")}

        success, msg, cookies = login_api.check_qrcode_status(session["qr_id"], session["code"], cookies)
        session["cookies"] = cookies
        logger.info(f"[login_check] qr_status success={success}, msg={msg}, has_web_session={'web_session' in cookies}")

        if success:
            # Mark as processing to prevent concurrent polls from interfering
            session["processing"] = True

            try:
                # Step 1: Get user info (best-effort, don't block on failure)
                try:
                    success2, user_info, cookies = login_api.get_user_info(cookies)
                    logger.info(f"[login_check] user_info success={success2}, nickname={user_info.get('nickname', '?')}")
                except Exception as e:
                    logger.warning(f"[login_check] get_user_info failed: {e}")
                    success2, user_info = False, {}

                # Step 2: Fallback web_session recovery
                if "web_session" not in cookies:
                    logger.info("[login_check] web_session missing, trying page visit recovery")
                    try:
                        cookies = login_api._try_get_session_from_page(cookies)
                    except Exception as e:
                        logger.warning(f"[login_check] page recovery failed: {e}")

                cookies_str = login_api.cookies_to_str(cookies)

                # Step 3: Save cookie IMMEDIATELY (even if verification fails)
                # The web_session is already in cookies, that's what matters
                settings.update(COOKIES=cookies_str)
                logger.info(f"[login_check] Cookie saved! length={len(cookies_str)}, has_web_session={'web_session' in cookies}")

                # Step 4: Best-effort verification (don't fail if this errors)
                nickname = "未知"
                try:
                    from apis.xhs_pc_apis import XHS_Apis
                    verify_ok, verify_msg, _ = XHS_Apis().get_user_self_info(cookies_str)
                    logger.info(f"[login_check] verify: ok={verify_ok}, msg={verify_msg[:100]}")
                    if success2:
                        nickname = user_info.get("nickname", "未知")
                except Exception as e:
                    logger.warning(f"[login_check] verify failed (cookie already saved): {e}")

                session["completed"] = True
                result_msg = f"登录成功！用户: {nickname}"
                session["result_message"] = result_msg
                LOGIN_SESSIONS.pop(session_id, None)
                return {"success": True, "message": result_msg, "cookies": cookies_str}
            except Exception as e:
                logger.exception(f"[login_check] post-scan processing error: {e}")
                # Even on error, try to save whatever cookies we have
                try:
                    cookies_str = login_api.cookies_to_str(session["cookies"])
                    if len(cookies_str) > 100:
                        settings.update(COOKIES=cookies_str)
                        session["completed"] = True
                        session["result_message"] = "登录成功（部分验证跳过）"
                        LOGIN_SESSIONS.pop(session_id, None)
                        return {"success": True, "message": "登录成功！Cookie已保存", "cookies": cookies_str}
                except:
                    pass
                LOGIN_SESSIONS.pop(session_id, None)
                return {"success": False, "message": f"登录处理异常: {str(e)[:80]}"}
        else:
            return {"success": False, "message": msg}
    except Exception as e:
        logger.exception(f"检查扫码状态异常: {e}")
        return {"success": False, "message": f"检查状态异常: {str(e)[:80]}"}


class PhoneSendRequest(BaseModel):
    phone: str


@router.post("/phone/send")
async def login_phone_send(req: PhoneSendRequest, user=Depends(get_current_user)):
    """Send phone verification code."""
    phone = req.phone.strip()
    if not phone:
        return {"success": False, "message": "请输入手机号"}
    try:
        _cleanup_login_sessions()
        from apis.xhs_pc_login_apis import XHSLoginApi
        login_api = XHSLoginApi()
        cookies = login_api.generate_init_cookies()
        success, msg, _ = login_api.send_phone_code(phone, cookies)
        session_id = f"phone_{int(time.time() * 1000)}"
        LOGIN_SESSIONS[session_id] = {
            "cookies": cookies, "login_api": login_api,
            "phone": phone, "type": "phone", "created_at": time.time(),
        }
        return {"success": success, "message": msg, "session_id": session_id}
    except Exception as e:
        return {"success": False, "message": str(e)}


class PhoneVerifyRequest(BaseModel):
    session_id: str
    code: str


@router.post("/phone/verify")
async def login_phone_verify(req: PhoneVerifyRequest, user=Depends(get_current_user)):
    """Verify phone code and login."""
    session = LOGIN_SESSIONS.get(req.session_id)
    if not session or session.get("type") != "phone":
        return {"success": False, "message": "会话不存在"}
    if time.time() - session["created_at"] > 300:
        LOGIN_SESSIONS.pop(req.session_id, None)
        return {"success": False, "message": "验证码已过期"}

    try:
        login_api = session["login_api"]
        success, msg, result = login_api.login_by_phone(session["phone"], req.code.strip(), session["cookies"])
        if not success:
            return {"success": False, "message": msg}

        cookies = result["cookies"]
        s2, user_info, cookies = login_api.get_user_info(cookies)
        cookies_str = login_api.cookies_to_str(cookies)
        settings.update(COOKIES=cookies_str)

        nickname = user_info.get("nickname", "未知") if s2 else "未知"
        LOGIN_SESSIONS.pop(req.session_id, None)
        return {"success": True, "message": f"登录成功！用户: {nickname}", "cookies": cookies_str}
    except Exception as e:
        return {"success": False, "message": f"登录异常: {str(e)}"}
