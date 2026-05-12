"""
Browser-based XHS login using Playwright with anti-detection stealth.

Strategy: Open XHS → screenshot QR → intercept the QR status API responses.
Only trust codeStatus==2 AFTER the QR screenshot has been taken and returned to user.
Uses stealth techniques to avoid triggering XHS anti-bot verification.
"""
import time
import base64
import threading
from typing import Optional, Dict, Any
from loguru import logger


# Stealth JS to inject before page loads — removes Playwright fingerprinting
STEALTH_JS = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// Override navigator.plugins to look like a real browser
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        return [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
        ];
    },
});

// Override navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en-US', 'en'],
});

// Override navigator.platform
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32',
});

// Fix chrome.runtime to look like a real browser
window.chrome = {
    runtime: {
        onConnect: { addListener: function() {} },
        onMessage: { addListener: function() {} },
        connect: function() {
            return { onMessage: { addListener: function() {} }, postMessage: function() {} };
        },
        sendMessage: function() {},
    },
    loadTimes: function() { return {}; },
    csi: function() { return {}; },
    app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } },
};

// Override navigator.permissions.query for notifications
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);

// Override WebGL vendor/renderer
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.apply(this, arguments);
};

// Remove automation-related properties
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
"""


class BrowserLoginSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status = "initializing"
        self.qr_image_b64: Optional[str] = None
        self.qr_url: Optional[str] = None
        self.cookies_str: Optional[str] = None
        self.error_message: Optional[str] = None
        self.created_at = time.time()
        self._browser_context = None
        self._page = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._login_confirmed = False
        self._qr_ready = False  # Only trust API responses after QR is shown
        self._intercepted_count = 0

        # ── 二次验证状态 ──────────────────────────────────────────────
        self.verification_type: Optional[str] = None  # "phone_sms" | "device_qr" | "captcha" | "slider" | "unknown"
        self.verification_data: Dict[str, Any] = {}   # 验证所需的截图/信息
        self.verification_pending = False              # 是否有等待用户处理的验证
        self.verification_result: Optional[dict] = None  # 用户提交的验证结果
        self.verification_screenshot_b64: Optional[str] = None  # 验证截图（base64）

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._cleanup()

    def _cleanup(self):
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
        except:
            pass
        try:
            if self._browser_context:
                self._browser_context.close()
        except:
            pass

    def _run(self):
        try:
            self._do_login()
        except Exception as e:
            logger.exception(f"[browser_login] {self.session_id} failed: {e}")
            self.status = "failed"
            self.error_message = str(e)[:200]
            self._cleanup()

    def _build_cookie_string(self, context):
        cookies = context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        xhs_cookies = []
        for c in cookies:
            if '.xiaohongshu.com' in c.get('domain', '') or c['name'] in (
                    'web_session', 'a1', 'webId', 'gid', 'abRequestId'):
                xhs_cookies.append(f"{c['name']}={c['value']}")
        for name in ['a1', 'webId', 'gid', 'web_session', 'abRequestId', 'webBuild',
                     'xsecappid', 'sec_poison_id', 'acw_tc', 'loadts', 'ets']:
            if name in cookie_dict and f"{name}=" not in '; '.join(xhs_cookies):
                xhs_cookies.append(f"{name}={cookie_dict[name]}")
        return '; '.join(xhs_cookies)

    def _on_response(self, response):
        """Intercept QR status API responses."""
        try:
            url = response.url

            if '/api/qrcode/userinfo' in url:
                self._intercepted_count += 1

                try:
                    body = response.json()
                    data = body.get('data', {})
                    code_status = data.get('codeStatus')

                    # Log every interception for debugging
                    logger.info(f"[browser_login] {self.session_id}: "
                                f"[#{self._intercepted_count}] /api/qrcode/userinfo response: "
                                f"codeStatus={code_status}, success={body.get('success')}, "
                                f"qr_ready={self._qr_ready}")

                    # ONLY accept codeStatus==2 if:
                    # 1. QR has been shown to user (qr_ready=True)
                    # 2. We haven't already confirmed
                    if code_status == 2 and self._qr_ready and not self._login_confirmed:
                        logger.info(f"[browser_login] {self.session_id}: "
                                    "*** LOGIN CONFIRMED *** codeStatus=2 (qr_ready=True)")
                        self._login_confirmed = True
                    elif code_status == 2 and not self._qr_ready:
                        logger.warning(f"[browser_login] {self.session_id}: "
                                      "codeStatus=2 but qr_ready=False — IGNORING (stale data?)")
                    elif code_status == 1:
                        logger.info(f"[browser_login] {self.session_id}: "
                                   "QR scanned, waiting for confirmation (codeStatus=1)")
                except Exception as e:
                    logger.debug(f"[browser_login] QR parse error: {e}")

        except Exception as e:
            logger.debug(f"[browser_login] interceptor error: {e}")

    def _do_login(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Use headed mode in non-headless to reduce detection,
            # but use headless=new (new headless mode less detectable)
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--start-maximized',
                ]
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                screen={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
                color_scheme='light',
                has_touch=False,
                java_script_enabled=True,
            )
            self._browser_context = context
            page = context.new_page()
            self._page = page

            # Inject stealth JS BEFORE any page loads
            page.add_init_script(STEALTH_JS)

            # Register interceptor BEFORE navigation
            page.on("response", self._on_response)

            logger.info(f"[browser_login] {self.session_id}: navigating to XHS (stealth mode)...")

            # Navigate to XHS explore page
            page.goto('https://www.xiaohongshu.com/explore', wait_until='domcontentloaded', timeout=30000)

            # Wait for page to fully load
            time.sleep(5)

            # Random mouse movement to appear more human-like
            try:
                page.mouse.move(500, 300)
                time.sleep(0.3)
                page.mouse.move(700, 400)
                time.sleep(0.2)
                page.mouse.move(600, 350)
                time.sleep(0.5)
            except:
                pass

            # === Screenshot QR code ===
            self.status = "waiting"
            qr_element = None
            for selector in ['.qrcode-img img', '.qr-code img', 'img[class*="qr"]',
                             'canvas[class*="qr"]', 'div[class*="qrcode"] canvas',
                             'div[class*="qr-code"] img', 'div.login-qrcode img',
                             '#login img', '.login-container img']:
                try:
                    qr_element = page.wait_for_selector(selector, timeout=3000)
                    if qr_element:
                        logger.info(f"[browser_login] {self.session_id}: found QR element with selector: {selector}")
                        break
                except:
                    continue

            if qr_element:
                try:
                    qr_element.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    screenshot = qr_element.screenshot(type='png')
                except:
                    screenshot = page.screenshot(type='png')
            else:
                logger.warning(f"[browser_login] {self.session_id}: no QR element found, using full page screenshot")
                screenshot = page.screenshot(type='png')

            self.qr_image_b64 = base64.b64encode(screenshot).decode()
            self.status = "scanning"

            # === CRITICAL: Mark QR as ready BEFORE waiting ===
            self._qr_ready = True
            logger.info(f"[browser_login] {self.session_id}: QR ready ({len(screenshot)} bytes), "
                        f"intercepted {self._intercepted_count} API calls so far. "
                        f"Waiting for user scan...")

            # Wait for login confirmation
            start_time = time.time()
            max_wait = 180

            while time.time() - start_time < max_wait:
                if self._stop_event.is_set():
                    return

                time.sleep(2)

                # ── 新增：检测二次验证 ──────────────────────────────
                if not self._login_confirmed and self._qr_ready:
                    self._detect_verification(page)

                # ── 新增：应用用户提交的验证结果 ────────────────────
                if self.verification_result:
                    self._apply_verification_result(page)

                if self._login_confirmed:
                    logger.info(f"[browser_login] {self.session_id}: "
                                "confirmed! Collecting cookies (NOT navigating away)...")

                    # Let page JS finish its login flow naturally
                    cookie_wait_start = time.time()
                    while time.time() - cookie_wait_start < 30:
                        time.sleep(2)
                        self.cookies_str = self._build_cookie_string(context)
                        if 'web_session=' in self.cookies_str:
                            self.status = "completed"
                            logger.info(f"[browser_login] {self.session_id}: "
                                        f"DONE! cookies={len(self.cookies_str)} chars")
                            self._cleanup()
                            return

                    logger.error(f"[browser_login] {self.session_id}: "
                                "confirmed but no web_session after 30s!")
                    self.status = "failed"
                    self.error_message = "登录成功但无法获取会话（请重试）"
                    self._cleanup()
                    return

            # Timeout
            logger.warning(f"[browser_login] {self.session_id}: timeout")
            self.status = "failed"
            self.error_message = "二维码已过期，请重新获取"
            self._cleanup()

    def _detect_verification(self, page) -> bool:
        """检测页面上是否出现二次验证弹窗"""
        try:
            import base64 as _b64

            # ── 设置更大视口以确保截图清晰可见 ──────────────────────────────
            try:
                page.set_viewport_size(width=1920, height=1080)
                time.sleep(0.5)
            except Exception:
                pass

            # === 手机验证码输入框检测 ===
            phone_inputs = page.query_selector_all('input[type="tel"], input[placeholder*="手机"], input[placeholder*="手机号"]')
            code_inputs = page.query_selector_all('input[placeholder*="验证码"], input[placeholder*="code"], input[placeholder*="Code"]')

            if phone_inputs and code_inputs and not self.verification_type:
                self.verification_type = "phone_sms"
                self.verification_pending = True
                try:
                    modal = page.query_selector('.modal, .dialog, [class*="verify"], [class*="captcha"], [class*="phone"]')
                    if modal:
                        screenshot = modal.screenshot(type='png')
                    else:
                        screenshot = page.screenshot(type='png', full_page=True)
                    self.verification_screenshot_b64 = _b64.b64encode(screenshot).decode()
                except Exception:
                    screenshot = page.screenshot(type='png', full_page=True)
                    self.verification_screenshot_b64 = _b64.b64encode(screenshot).decode()

                self.verification_data = {
                    "message": "小红书要求输入手机验证码",
                    "hint": "请查看截图中的页面，输入收到的手机验证码",
                }
                self.status = "secondary_verify"
                logger.info(f"[browser_login] {self.session_id}: 检测到手机验证码二次验证")
                return True

            # === 设备扫码二维码检测 ===
            qr_modal = page.query_selector('[class*="qrcode"][class*="modal"], [class*="qr"][class*="verify"], [class*="scan"][class*="verify"]')
            if qr_modal and not self._login_confirmed and not self.verification_type:
                self.verification_type = "device_qr"
                self.verification_pending = True
                try:
                    screenshot = qr_modal.screenshot(type='png')
                    self.verification_screenshot_b64 = _b64.b64encode(screenshot).decode()
                except Exception:
                    screenshot = page.screenshot(type='png', full_page=True)
                    self.verification_screenshot_b64 = _b64.b64encode(screenshot).decode()

                self.verification_data = {
                    "message": "小红书要求原设备扫码验证",
                    "hint": "请打开小红书APP，使用扫一扫扫描页面中的二维码",
                }
                self.status = "secondary_verify"
                logger.info(f"[browser_login] {self.session_id}: 检测到设备扫码二次验证")
                return True

            # === 图形验证码/CAPTCHA检测 ===
            captcha_img = page.query_selector('img[class*="captcha"], img[class*="verify"], canvas[class*="captcha"], [class*="slider"]')
            if captcha_img and not self.verification_type:
                self.verification_type = "captcha"
                self.verification_pending = True
                try:
                    screenshot = captcha_img.screenshot(type='png')
                    self.verification_screenshot_b64 = _b64.b64encode(screenshot).decode()
                except Exception:
                    screenshot = page.screenshot(type='png', full_page=True)
                    self.verification_screenshot_b64 = _b64.b64encode(screenshot).decode()

                self.verification_data = {
                    "message": "小红书要求完成图形验证码",
                    "hint": "请查看截图并输入验证码",
                }
                self.status = "secondary_verify"
                logger.info(f"[browser_login] {self.session_id}: 检测到图形验证码")
                return True

            # === URL变化检测（跳转到验证页面）===
            current_url = page.url
            if any(kw in current_url.lower() for kw in ('verify', 'captcha', 'phone', 'sms')):
                if not self.verification_type:
                    self.verification_type = "unknown"
                    self.verification_pending = True
                    screenshot = page.screenshot(type='png', full_page=True)
                    self.verification_screenshot_b64 = _b64.b64encode(screenshot).decode()
                    self.verification_data = {
                        "message": "小红书跳转到验证页面",
                        "hint": "请查看截图中的页面内容",
                        "url": current_url,
                    }
                    self.status = "secondary_verify"
                    logger.info(f"[browser_login] {self.session_id}: URL变化检测到验证页面: {current_url}")
                    return True

        except Exception as e:
            logger.debug(f"[browser_login] verification detection error: {e}")

        return False

    def _apply_verification_result(self, page) -> bool:
        """将用户提交的验证结果应用到页面"""
        if not self.verification_result:
            return False

        result = self.verification_result
        vtype = result.get("type")

        try:
            if vtype == "phone_sms":
                code = result.get("code", "")
                if code:
                    code_input = page.query_selector('input[placeholder*="验证码"], input[placeholder*="code"]')
                    if code_input:
                        code_input.fill(code)
                        time.sleep(0.5)
                        confirm_btn = page.query_selector('button:has-text("确"), button:has-text("验证"), button:has-text("登录"), button[type="submit"]')
                        if confirm_btn:
                            confirm_btn.click()
                        logger.info(f"[browser_login] {self.session_id}: 已填入手机验证码并提交")
                        self.verification_pending = False
                        self.verification_result = None
                        self.verification_type = None
                        return True
                    else:
                        logger.warning(f"[browser_login] {self.session_id}: 未找到验证码输入框")

            elif vtype == "captcha":
                code = result.get("code", "")
                if code:
                    captcha_input = page.query_selector('input[placeholder*="验证"], input[placeholder*="captcha"]')
                    if captcha_input:
                        captcha_input.fill(code)
                        time.sleep(0.5)
                        confirm_btn = page.query_selector('button:has-text("确"), button:has-text("提交")')
                        if confirm_btn:
                            confirm_btn.click()
                        logger.info(f"[browser_login] {self.session_id}: 已填入验证码并提交")
                        self.verification_pending = False
                        self.verification_result = None
                        self.verification_type = None
                        return True

            elif vtype == "device_qr":
                logger.info(f"[browser_login] {self.session_id}: 用户确认已扫码，等待页面跳转...")
                self.verification_pending = False
                self.verification_result = None
                self.verification_type = None
                return True

            elif vtype == "refresh":
                import base64 as _b64
                screenshot = page.screenshot(type='png', full_page=True)
                self.verification_screenshot_b64 = _b64.b64encode(screenshot).decode()
                self.verification_result = None
                return True

        except Exception as e:
            logger.error(f"[browser_login] {self.session_id}: apply verification error: {e}")

        self.verification_result = None
        return False

    def submit_verification(self, verification_type: str, code: str = "") -> bool:
        """接收前端提交的验证结果"""
        self.verification_result = {
            "type": verification_type,
            "code": code,
        }
        logger.info(f"[browser_login] {self.session_id}: 收到验证提交 type={verification_type}")
        return True

    def get_status(self) -> Dict[str, Any]:
        result = {
            "status": self.status,
            "qr_image_b64": self.qr_image_b64 if self.status in ("waiting", "scanning") else None,
            "qr_url": self.qr_url,
            "cookies_str": self.cookies_str if self.status == "completed" else None,
            "error_message": self.error_message,
            "elapsed": int(time.time() - self.created_at),
        }
        # 二次验证信息
        if self.status == "secondary_verify":
            result["verification_type"] = self.verification_type
            result["verification_data"] = self.verification_data
            result["verification_screenshot_b64"] = self.verification_screenshot_b64
            result["verification_pending"] = self.verification_pending
        return result


_browser_sessions: Dict[str, BrowserLoginSession] = {}


def create_browser_session() -> BrowserLoginSession:
    session_id = f"browser_{int(time.time() * 1000)}"
    session = BrowserLoginSession(session_id)
    _browser_sessions[session_id] = session
    session.start()
    return session


def get_browser_session(session_id: str) -> Optional[BrowserLoginSession]:
    return _browser_sessions.get(session_id)


def cleanup_old_sessions():
    now = time.time()
    expired = [sid for sid, s in _browser_sessions.items() if now - s.created_at > 600]
    for sid in expired:
        session = _browser_sessions.pop(sid, None)
        if session:
            session.stop()
