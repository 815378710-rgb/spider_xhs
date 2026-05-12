import json
import time
import random
import uuid

import requests
import qrcode
from loguru import logger

from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.http_util import REQUEST_TIMEOUT
from xhs_utils.xhs_util import generate_headers, generate_xs_xs_common, splice_str
from xhs_utils.common_util import generate_a1, generate_web_id


class XHSLoginApi:
    def __init__(self):
        self.base_url = "https://edith.xiaohongshu.com"
        self.as_url = "https://as.xiaohongshu.com"
        self.home_url = 'https://www.xiaohongshu.com/explore'
        self._ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'

    def _sec_headers(self):
        return {
            'user-agent': self._ua,
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/json;charset=UTF-8',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'origin': 'https://www.xiaohongshu.com',
            'referer': 'https://www.xiaohongshu.com/',
        }

    def _fetch_sec_cookies(self, cookies):
        api = '/api/sec/v1/scripting'
        data = {"callFrom": "web", "callback": "", "type": "ds", "appId": "xhs-pc-web"}
        xs, xt, xs_common = generate_xs_xs_common(cookies['a1'], api, data)
        headers = self._sec_headers()
        headers['x-s'] = xs
        headers['x-t'] = str(xt)
        headers['x-s-common'] = xs_common
        data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        try:
            resp = requests.post(self.as_url + api, headers=headers, cookies=cookies,
                                 data=data_str.encode('utf-8'), timeout=REQUEST_TIMEOUT)
            return resp.json().get('data', {}).get('secPoisonId')
        except Exception as e:
            logger.debug(f'fetch sec_poison_id failed: {e}')
            return None

    def _fetch_gid(self, cookies):
        api = '/api/sec/v1/shield/webprofile'
        data = {"platform": "Windows", "sdkVersion": "4.3.5", "svn": "2", "profileData": ""}
        xs, xt, xs_common = generate_xs_xs_common(cookies['a1'], api, data)
        headers = self._sec_headers()
        headers['x-s'] = xs
        headers['x-t'] = str(xt)
        headers['x-s-common'] = xs_common
        data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        try:
            resp = requests.post(self.as_url + api, headers=headers, cookies=cookies,
                                 data=data_str.encode('utf-8'), timeout=REQUEST_TIMEOUT)
            for k, v in resp.cookies.items():
                cookies[k] = v
            return cookies.get('gid')
        except Exception as e:
            logger.debug(f'fetch gid failed: {e}')
            return None

    def generate_init_cookies(self):
        ts = int(time.time() * 1000)
        a1 = generate_a1()
        web_id = generate_web_id(a1)
        cookies = {
            'abRequestId': str(uuid.uuid4()),
            'ets': str(ts),
            'webBuild': '6.7.4',
            'xsecappid': 'xhs-pc-web',
            'loadts': str(ts + random.randint(50, 200)),
            'a1': a1,
            'webId': web_id,
        }
        sec_poison_id = self._fetch_sec_cookies(cookies)
        if sec_poison_id:
            cookies['sec_poison_id'] = sec_poison_id
        gid = self._fetch_gid(cookies)
        if gid:
            cookies['gid'] = gid
        return cookies

    # ──────────────────── 扫码登录 ────────────────────

    def generate_qrcode(self, cookies):
        api = '/api/sns/web/v1/login/qrcode/create'
        data = {"qr_type": 1}
        headers, data = generate_headers(cookies['a1'], api, data)
        resp = requests.post(self.base_url + api, headers=headers, cookies=cookies, data=data,
                             timeout=REQUEST_TIMEOUT)
        for k, v in resp.cookies.items():
            cookies[k] = v
        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '未知错误'), None
        d = res.get('data') or {}
        if not all(k in d for k in ('qr_id', 'code', 'url')):
            return False, res.get('msg', '二维码响应缺少必要字段'), {'cookies': cookies, 'res_json': res}
        return True, '成功', {
            'cookies': cookies,
            'qr_id': d['qr_id'],
            'code': d['code'],
            'qr_url': d['url'],
        }

    def check_qrcode_status(self, qr_id, code, cookies):
        """轮询扫码状态 — 两步流程
        Step 1: POST /api/qrcode/userinfo 检查码状态
        Step 2: status==2 时 GET /api/sns/web/v1/login/qrcode/status 获取 session
        """
        # Step 1: 检查二维码状态
        api = '/api/qrcode/userinfo'
        data = {"qrId": qr_id, "code": code}
        headers, data = generate_headers(cookies['a1'], api, data)
        resp = requests.post(self.base_url + api, headers=headers, cookies=cookies,
                             data=data, timeout=REQUEST_TIMEOUT)
        for k, v in resp.cookies.items():
            cookies[k] = v

        res = resp.json()
        status = (res.get('data') or {}).get('codeStatus')
        logger.info(f"[qr_status] status={status}, resp_success={res.get('success')}, "
                     f"resp_full={json.dumps(res, ensure_ascii=False)[:500]}")

        if status is None:
            return False, res.get('msg', '二维码状态未知'), cookies

        # Step 2: 扫码成功 → 获取 session
        if status == 2:
            cookies = self._login_by_qrcode_status(qr_id, code, cookies)
            logger.info(f"[qr_status] after session fetch: cookies keys={list(cookies.keys())}, "
                         f"has_web_session={'web_session' in cookies}")

            # 兜底：如果仍无 web_session，尝试页面访问
            if 'web_session' not in cookies:
                logger.info(f"[qr_status] web_session still missing, trying page visit recovery")
                cookies = self._try_get_session_from_page(cookies)

        status_map = {
            0: (False, '请扫描二维码'),
            1: (False, '请确认登录'),
            2: (True, '验证成功'),
            3: (False, '二维码已过期'),
        }
        success, msg = status_map.get(status, (False, f'未知状态: {status}'))
        return success, msg, cookies

    def _login_by_qrcode_status(self, qr_id, code, cookies):
        """扫码成功后，调用 qrcode/status 获取 session"""
        api = '/api/sns/web/v1/login/qrcode/status'
        params = {"qr_id": qr_id, "code": code}
        splice_api = splice_str(api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api, method='GET')
        resp = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies,
                            timeout=REQUEST_TIMEOUT)
        for k, v in resp.cookies.items():
            cookies[k] = v

        res = resp.json()
        logger.info(f"[qr_session] resp={json.dumps(res, ensure_ascii=False)[:500]}")

        if res.get('success') and 'login_info' in (res.get('data') or {}):
            login_info = res['data']['login_info']
            if 'session' in login_info and 'web_session' not in cookies:
                cookies['web_session'] = login_info['session']
                logger.info(f"[qr_session] got web_session from login_info.session")

        # 兜底：也检查 data 顶层
        d = res.get('data') or {}
        for key in ('session', 'web_session'):
            if key in d and d[key] and 'web_session' not in cookies:
                cookies['web_session'] = d[key]
                logger.info(f"[qr_session] got web_session from data.{key}")

        return cookies

    def _try_get_session_from_page(self, cookies):
        """尝试通过 requests.Session 访问页面触发 Set-Cookie"""
        sess = requests.Session()
        sess.headers.update({
            'user-agent': self._ua,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'zh-CN,zh;q=0.9',
        })
        sess.cookies.update(cookies)

        # 访问首页，跟随重定向
        try:
            resp = sess.get('https://www.xiaohongshu.com/explore',
                            timeout=REQUEST_TIMEOUT, allow_redirects=True)
            logger.info(f"[page_session] explore status={resp.status_code}, final_url={resp.url[:80]}")
            # 从 Session cookie jar 同步回 cookies dict
            for k, v in sess.cookies.items():
                cookies[k] = v
                if k == 'web_session':
                    logger.info(f"[page_session] got web_session from /explore!")
                    return cookies
            logger.info(f"[page_session] explore cookies: {list(sess.cookies.keys())}")
        except Exception as e:
            logger.warning(f"[page_session] explore failed: {e}")

        # 再试 API
        try:
            api = '/api/sns/web/v2/user/me'
            h2, _ = generate_headers(cookies['a1'], api)
            resp2 = sess.get(self.base_url + api, headers=h2, timeout=REQUEST_TIMEOUT)
            for k, v in sess.cookies.items():
                cookies[k] = v
                if k == 'web_session':
                    logger.info(f"[page_session] got web_session from /user/me!")
                    return cookies
            logger.info(f"[page_session] user/me resp.cookies: {dict(resp2.cookies)}")
            r2 = resp2.json()
            if r2.get('success'):
                logger.info(f"[page_session] user/me success! nickname={r2.get('data', {}).get('nickname', '?')}")
                # user/me 成功说明登录态有效，但 web_session 不在 cookie 里
                # 可能需要手动构造
        except Exception as e:
            logger.warning(f"[page_session] user/me failed: {e}")

        return cookies

    # ──────────────────── 验证码登录 ────────────────────

    def send_phone_code(self, phone, cookies, zone='86'):
        api = '/api/sns/web/v2/login/send_code'
        params = {"phone": phone, "zone": zone, "type": "login"}
        splice_api = splice_str(api, params)
        headers, _ = generate_headers(cookies['a1'], splice_api)
        resp = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies,
                            timeout=REQUEST_TIMEOUT)
        res = resp.json()
        return res.get('success', False), res.get('msg', ''), res

    def login_by_phone(self, phone, code, cookies, zone='86'):
        check_api = '/api/sns/web/v1/login/check_code'
        params = {"phone": phone, "zone": zone, "code": code}
        splice_api = splice_str(check_api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api)
        resp = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies,
                            timeout=REQUEST_TIMEOUT)
        res = resp.json()
        logger.info(f"[login_by_phone] check_code resp: success={res.get('success')}, msg={res.get('msg', '')}")
        if not res.get('success'):
            return False, res.get('msg', '验证码验证失败'), {'cookies': cookies}
        mobile_token = (res.get('data') or {}).get('mobile_token')
        if not mobile_token:
            return False, res.get('msg', '验证码响应缺少 mobile_token'), {'cookies': cookies, 'res_json': res}
        logger.info(f"[login_by_phone] got mobile_token={mobile_token[:20]}...")

        login_api = '/api/sns/web/v2/login/code'
        data = {"mobile_token": mobile_token, "zone": zone, "phone": phone}
        headers, data = generate_headers(cookies['a1'], login_api, data)
        resp = requests.post(self.base_url + login_api, headers=headers, cookies=cookies, data=data,
                             timeout=REQUEST_TIMEOUT)
        logger.info(f"[login_by_phone] Set-Cookie: {dict(resp.headers).get('Set-Cookie', 'NONE')}")
        for k, v in resp.cookies.items():
            cookies[k] = v

        res = resp.json()
        logger.info(f"[login_by_phone] login/code resp: success={res.get('success')}, data_keys={list((res.get('data') or {}).keys())}")
        if not res.get('success'):
            return False, res.get('msg', '登录失败'), {'cookies': cookies, 'res_json': res}

        # Step 1: 从响应获取 session
        sess = (res.get('data') or {}).get('session')
        if sess:
            cookies['web_session'] = sess
            logger.info(f"[login_by_phone] got session from response data")

        # Step 2: Session recovery
        if 'web_session' not in cookies:
            logger.info(f"[login_by_phone] session not in response, trying page visit recovery")
            cookies = self._try_get_session_from_page(cookies)

        # Step 3: 最终检查
        if 'web_session' not in cookies:
            logger.error(f"[login_by_phone] recovery failed. cookies keys={list(cookies.keys())}")
            return False, '登录成功但无法获取会话（请刷新页面重试）', {'cookies': cookies, 'res_json': res}

        logger.info(f"[login_by_phone] final cookies keys={list(cookies.keys())}")
        return True, '成功', {'cookies': cookies, 'res_json': res}

    # ──────────────────── 工具方法 ────────────────────

    def get_user_info(self, cookies):
        api = '/api/sns/web/v2/user/me'
        headers, _ = generate_headers(cookies['a1'], api)
        resp = requests.get(self.base_url + api, headers=headers, cookies=cookies,
                            timeout=REQUEST_TIMEOUT)
        for k, v in resp.cookies.items():
            cookies[k] = v
        res = resp.json()
        logger.info(f"[get_user_info] success={res.get('success')}, nickname={res.get('data', {}).get('nickname', '?')}")
        return res.get('success', False), res.get('data', {}), cookies

    @staticmethod
    def cookies_to_str(cookies):
        return '; '.join(f'{k}={v}' for k, v in cookies.items())

    @staticmethod
    def show_qrcode_terminal(url):
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

    @staticmethod
    def show_qrcode_image(url):
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.show()

    def qrcode_login(self, show_in_terminal=True):
        logger.info('[1/4] 正在生成初始cookies...')
        cookies = self.generate_init_cookies()
        logger.info(f'{cookies}')

        logger.info('[2/4] 正在获取二维码...')
        success, msg, qr_data = self.generate_qrcode(cookies)
        if not success:
            logger.error(f'获取二维码失败: {msg}')
            return None
        cookies = qr_data['cookies']

        logger.info('请使用小红书APP扫描以下二维码:')
        if show_in_terminal:
            self.show_qrcode_terminal(qr_data['qr_url'])
        else:
            self.show_qrcode_image(qr_data['qr_url'])

        logger.info('[3/4] 等待扫码...')
        while True:
            success, msg, cookies = self.check_qrcode_status(
                qr_data['qr_id'], qr_data['code'], cookies
            )
            if success:
                logger.info(msg)
                break
            if msg == '二维码已过期':
                logger.error(msg)
                return None
            time.sleep(2)

        logger.info('[4/4] 验证登录状态...')
        success, user_info, cookies = self.get_user_info(cookies)
        if success:
            logger.info(f'用户: {user_info.get("nickname", "未知")} (RedID: {user_info.get("red_id", "未知")})')
        else:
            logger.warning('获取用户信息失败，但cookies可能仍有效')

        cookies_str = self.cookies_to_str(cookies)
        logger.success(f'登录成功!\ncookies:\n{cookies_str}')
        return cookies_str

    def phone_login(self):
        logger.info('[1/4] 正在生成初始cookies...')
        cookies = self.generate_init_cookies()
        logger.info(f'a1={cookies["a1"]}')

        phone = input('请输入手机号: ')
        logger.info('[2/4] 正在发送验证码...')
        success, msg, _ = self.send_phone_code(phone, cookies)
        if not success:
            logger.error(f'发送失败: {msg}')
            return None
        logger.info('验证码已发送')

        code = input('请输入验证码: ')
        logger.info('[3/4] 正在验证...')
        success, msg, result = self.login_by_phone(phone, code, cookies)
        if not success:
            logger.error(f'验证失败: {msg}')
            return None
        cookies = result['cookies']

        logger.info('[4/4] 验证登录状态...')
        success, user_info, cookies = self.get_user_info(cookies)
        if success:
            logger.info(f'用户: {user_info.get("nickname", "未知")} (RedID: {user_info.get("red_id", "未知")})')

        cookies_str = self.cookies_to_str(cookies)
        logger.success(f'登录成功!\ncookies:\n{cookies_str}')
        return cookies_str


if __name__ == '__main__':
    login_api = XHSLoginApi()
    # cookies_str = login_api.qrcode_login(show_in_terminal=True)
    cookies_str = login_api.phone_login()

    xhs_apis = XHS_Apis()
    user_url = 'https://www.xiaohongshu.com/user/profile/67a332a2000000000d008358?xsec_token=ABTf9yz4cLHhTycIlksF0jOi1yIZgfcaQ6IXNNGdKJ8xg=&xsec_source=pc_feed'
    success, msg, user_info = xhs_apis.search_note("888666", cookies_str)
    print(success, msg, user_info)
