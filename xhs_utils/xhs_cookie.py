"""
Cookie 池管理模块
负责 Cookie 的存储、验证、轮换、自动刷新

架构：
- config/xhs_cookie_pool.json → Cookie 池存储文件
- 每个 Cookie 记录：{cookies_str, username, fetch_date, is_valid, last_check}
- 自动验证有效性（调用 get_user_self_info）
- 自动轮换（失效时切换下一个）
- 定时刷新（每日 23:30 自动获取新 Cookie）
"""
import json
import os
import time
from datetime import datetime
from loguru import logger


class XhsCookie:
    def __init__(self, config_dir=None):
        self.config_dir = config_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config"
        )
        os.makedirs(self.config_dir, exist_ok=True)
        self.cookie_pool_file = os.path.join(self.config_dir, "xhs_cookie_pool.json")
        self.pool = self._load_pool()

    def _load_pool(self):
        """加载 Cookie 池"""
        if os.path.exists(self.cookie_pool_file):
            try:
                with open(self.cookie_pool_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_pool(self):
        """保存 Cookie 池"""
        os.makedirs(os.path.dirname(self.cookie_pool_file), exist_ok=True)
        with open(self.cookie_pool_file, 'w', encoding='utf-8') as f:
            json.dump(self.pool, f, ensure_ascii=False, indent=2)

    def add_cookie(self, cookies_str, username="未知", is_valid=True):
        """添加 Cookie 到池中（去重）"""
        # 检查是否已存在（通过 a1 字段判断）
        from .cookie_util import trans_cookies
        new_ck = trans_cookies(cookies_str)
        new_a1 = new_ck.get('a1', '')

        for item in self.pool:
            existing_ck = trans_cookies(item.get('cookies_str', ''))
            if existing_ck.get('a1') == new_a1:
                # 更新已存在的
                item['cookies_str'] = cookies_str
                item['username'] = username
                item['is_valid'] = is_valid
                item['last_check'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self._save_pool()
                logger.info(f"更新已有 Cookie: {username}")
                return True

        # 新增
        self.pool.append({
            'cookies_str': cookies_str,
            'username': username,
            'fetch_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'is_valid': is_valid,
            'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
        self._save_pool()
        logger.info(f"新增 Cookie: {username}，池中总数: {len(self.pool)}")
        return True

    def remove_cookie(self, index=None, a1=None):
        """移除 Cookie（按索引或 a1）"""
        if a1:
            from .cookie_util import trans_cookies
            self.pool = [
                item for item in self.pool
                if trans_cookies(item.get('cookies_str', '')).get('a1') != a1
            ]
        elif index is not None and 0 <= index < len(self.pool):
            self.pool.pop(index)
        self._save_pool()

    def get_valid_cookies(self):
        """获取所有有效的 Cookie"""
        return [item for item in self.pool if item.get('is_valid', False)]

    def get_best_cookie(self):
        """获取当前最佳可用 Cookie（优先选最近验证过的）"""
        valid = self.get_valid_cookies()
        if not valid:
            return None
        # 按 last_check 降序排列，选最近验证过的
        valid.sort(key=lambda x: x.get('last_check', ''), reverse=True)
        return valid[0]['cookies_str']

    def validate_cookie(self, cookies_str):
        """验证 Cookie 是否有效"""
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from apis.xhs_pc_apis import XHS_Apis
            xhs = XHS_Apis()
            success, msg, data = xhs.get_user_self_info(cookies_str)
            if success:
                nickname = data.get('data', {}).get('basic_info', {}).get('nickname', '未知')
                return True, nickname
            return False, msg
        except Exception as e:
            return False, str(e)

    def validate_all(self):
        """验证池中所有 Cookie 的有效性"""
        results = {'valid': 0, 'invalid': 0, 'details': []}
        for i, item in enumerate(self.pool):
            success, info = self.validate_cookie(item['cookies_str'])
            item['is_valid'] = success
            item['last_check'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if success:
                item['username'] = info
                results['valid'] += 1
            else:
                results['invalid'] += 1
            results['details'].append({
                'index': i,
                'username': item.get('username', '未知'),
                'is_valid': success,
                'info': info,
            })
            logger.info(f"验证 Cookie [{i}] {item.get('username', '?')}: {'✅' if success else '❌'} {info}")
        self._save_pool()
        return results

    def auto_update(self):
        """自动更新 Cookie 池（验证 + 清理失效）"""
        logger.info("开始自动更新 Cookie 池...")
        results = self.validate_all()

        # 移除失效的
        before = len(self.pool)
        self.pool = [item for item in self.pool if item.get('is_valid', False)]
        after = len(self.pool)
        removed = before - after
        if removed:
            self._save_pool()
            logger.info(f"清理了 {removed} 个失效 Cookie")

        return {
            'valid': results['valid'],
            'invalid': results['invalid'],
            'removed': removed,
            'total': len(self.pool),
        }

    def fetch_new_cookie(self):
        """自动获取新 Cookie（调用扫码登录流程）"""
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from apis.xhs_pc_login_apis import XHSLoginApi

        login_api = XHSLoginApi()

        # Step 1: 生成初始 Cookie
        logger.info("[1/4] 生成初始 Cookie...")
        cookies = login_api.generate_init_cookies()

        # Step 2: 获取二维码
        logger.info("[2/4] 获取二维码...")
        success, msg, qr_data = login_api.generate_qrcode(cookies)
        if not success:
            return {
                'success': False,
                'message': f'获取二维码失败: {msg}',
                'qr_url': None,
                'session_id': None,
            }

        # 返回二维码信息，等待用户扫码
        session_id = f"auto_{int(time.time() * 1000)}"
        return {
            'success': True,
            'message': '二维码已生成',
            'qr_url': qr_data['qr_url'],
            'session_id': session_id,
            'qr_id': qr_data['qr_id'],
            'code': qr_data['code'],
            'cookies': qr_data['cookies'],
            'login_api': login_api,
        }

    def complete_fetch(self, qr_id, code, cookies, login_api):
        """完成扫码登录，获取 Cookie 并加入池"""
        # Step 3: 检查扫码状态
        logger.info("[3/4] 检查扫码状态...")
        success, msg, cookies = login_api.check_qrcode_status(qr_id, code, cookies)
        if not success:
            return {'success': False, 'message': msg}

        # Step 4: 获取用户信息
        logger.info("[4/4] 获取用户信息...")
        success2, user_info, cookies = login_api.get_user_info(cookies)
        cookies_str = login_api.cookies_to_str(cookies)

        nickname = '未知'
        if success2:
            nickname = user_info.get('nickname', '未知')

        # 加入 Cookie 池
        self.add_cookie(cookies_str, username=nickname, is_valid=True)

        return {
            'success': True,
            'message': f'获取成功！用户: {nickname}',
            'cookies': cookies_str,
            'username': nickname,
        }

    def get_pool_info(self):
        """获取 Cookie 池概览"""
        return {
            'total': len(self.pool),
            'valid': len(self.get_valid_cookies()),
            'invalid': len(self.pool) - len(self.get_valid_cookies()),
            'cookies': [
                {
                    'index': i,
                    'username': item.get('username', '未知'),
                    'is_valid': item.get('is_valid', False),
                    'fetch_date': item.get('fetch_date', ''),
                    'last_check': item.get('last_check', ''),
                }
                for i, item in enumerate(self.pool)
            ],
        }
