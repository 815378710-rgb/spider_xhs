"""
登录路由 — 扫码登录 + 手机登录
"""
import time
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
        success, msg, cookies = login_api.check_qrcode_status(session["qr_id"], session["code"], cookies)
        session["cookies"] = cookies

        if success:
            success2, user_info, cookies = login_api.get_user_info(cookies)
            if "web_session" not in cookies:
                cookies = login_api._try_get_session_from_page(cookies)
            cookies_str = login_api.cookies_to_str(cookies)

            verify_ok, verify_msg, _ = __import__("apis.xhs_pc_apis", fromlist=["XHS_Apis"]).XHS_Apis().get_user_self_info(cookies_str)

            if not verify_ok and "web_session" not in cookies:
                LOGIN_SESSIONS.pop(session_id, None)
                return {"success": False, "message": f"Cookie 验证失败: {verify_msg[:80]}"}

            settings.update(COOKIES=cookies_str)
            nickname = user_info.get("nickname", "未知") if success2 else "未知"
            LOGIN_SESSIONS.pop(session_id, None)
            return {"success": True, "message": f"登录成功！用户: {nickname}", "cookies": cookies_str}
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
