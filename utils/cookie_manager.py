"""
Cookie安全管理器 — Fernet加密存储 + 有效性验证
- 首次运行自动生成Fernet密钥，持久化到 config/fernet.key
- 所有Cookie内容加密后存储
- 支持a1值提取（签名核心参数）
- Cookie有效性健康检查
"""
import os
import json
import base64
from datetime import datetime
from loguru import logger

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None
    logger.warning("cryptography未安装，Cookie加密不可用。请运行: pip install cryptography")


# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")
os.makedirs(_CONFIG_DIR, exist_ok=True)

_FERNET_KEY_PATH = os.path.join(_CONFIG_DIR, "fernet.key")
_STORAGE_PATH = os.path.join(_CONFIG_DIR, "cookies_encrypted.json")


class CookieManager:
    """Cookie安全管理器"""

    def __init__(self, storage_path=None):
        self._storage_path = storage_path or _STORAGE_PATH
        self._fernet = None
        self._init_fernet()

    def _init_fernet(self):
        """初始化Fernet实例"""
        if Fernet is None:
            logger.warning("[CookieManager] cryptography未安装，加密功能不可用")
            return
        try:
            key = self._ensure_fernet_key()
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            logger.error(f"[CookieManager] Fernet初始化失败: {e}")

    def _ensure_fernet_key(self) -> str:
        """确保Fernet密钥存在，不存在则生成并持久化"""
        # 优先读取config/fernet.key文件
        if os.path.exists(_FERNET_KEY_PATH):
            with open(_FERNET_KEY_PATH, "r") as f:
                key = f.read().strip()
            if key:
                return key

        # 从settings读取
        try:
            from core.config import settings
            if settings.FERNET_KEY:
                # 持久化到文件
                with open(_FERNET_KEY_PATH, "w") as f:
                    f.write(settings.FERNET_KEY)
                return settings.FERNET_KEY
        except Exception:
            pass

        # 生成新密钥并持久化
        key = Fernet.generate_key().decode()
        with open(_FERNET_KEY_PATH, "w") as f:
            f.write(key)
        logger.info(f"[CookieManager] 新Fernet密钥已生成并保存到 {_FERNET_KEY_PATH}")
        return key

    def _load_storage(self) -> dict:
        """加载加密存储"""
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_storage(self, data: dict):
        """保存加密存储"""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _encrypt(self, text: str) -> str:
        """加密文本"""
        if not self._fernet:
            return text  # 降级：无加密能力时明文存储
        try:
            return self._fernet.encrypt(text.encode()).decode()
        except Exception as e:
            logger.error(f"[CookieManager] 加密失败: {e}")
            return text

    def _decrypt(self, encrypted: str) -> str:
        """解密文本"""
        if not self._fernet:
            return encrypted  # 降级：无加密能力时当做明文
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except Exception as e:
            logger.error(f"[CookieManager] 解密失败: {e}")
            return encrypted

    def save_cookie(self, cookie_str: str, name: str = "default") -> bool:
        """加密存储Cookie"""
        try:
            data = self._load_storage()
            encrypted = self._encrypt(cookie_str)
            data[name] = {
                "cookies_encrypted": encrypted,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._save_storage(data)
            logger.info(f"[CookieManager] Cookie已保存: {name}")
            return True
        except Exception as e:
            logger.error(f"[CookieManager] 保存Cookie失败: {e}")
            return False

    def load_cookie(self, name: str = "default") -> str | None:
        """解密读取Cookie"""
        try:
            data = self._load_storage()
            entry = data.get(name)
            if not entry:
                return None
            encrypted = entry.get("cookies_encrypted", "")
            if not encrypted:
                return None
            return self._decrypt(encrypted)
        except Exception as e:
            logger.error(f"[CookieManager] 读取Cookie失败: {e}")
            return None

    def extract_a1(self, name: str = "default") -> str | None:
        """从Cookie中提取a1值（签名核心参数）"""
        cookie_str = self.load_cookie(name)
        if not cookie_str:
            return None
        try:
            from xhs_utils.cookie_util import trans_cookies
            cookies = trans_cookies(cookie_str)
            return cookies.get("a1")
        except Exception as e:
            logger.error(f"[CookieManager] 提取a1失败: {e}")
            # 简单正则提取
            import re
            m = re.search(r'a1=([^;]+)', cookie_str)
            return m.group(1) if m else None

    def delete_cookie(self, name: str = "default") -> bool:
        """删除指定Cookie"""
        try:
            data = self._load_storage()
            if name in data:
                del data[name]
                self._save_storage(data)
                logger.info(f"[CookieManager] Cookie已删除: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"[CookieManager] 删除Cookie失败: {e}")
            return False

    def list_cookies(self) -> list[dict]:
        """列出所有Cookie（不解密内容，只显示name和元数据）"""
        try:
            data = self._load_storage()
            result = []
            for name, entry in data.items():
                result.append({
                    "name": name,
                    "updated_at": entry.get("updated_at", ""),
                })
            return result
        except Exception as e:
            logger.error(f"[CookieManager] 列出Cookie失败: {e}")
            return []

    def health_check(self, cookie_str: str) -> dict:
        """验证Cookie有效性 — GET /api/sns/web/v1/user/self"""
        try:
            import sys
            sys.path.insert(0, _PROJECT_ROOT)
            from apis.xhs_pc_apis import XHS_Apis
            xhs = XHS_Apis()
            success, msg, data = xhs.get_user_self_info(cookie_str)
            if success:
                nickname = data.get("data", {}).get("basic_info", {}).get("nickname", "未知")
                return {"valid": True, "username": nickname, "error": ""}
            else:
                return {"valid": False, "username": "", "error": msg}
        except Exception as e:
            return {"valid": False, "username": "", "error": str(e)[:100]}

    def get_fernet_key(self) -> str:
        """获取当前Fernet密钥"""
        return self._ensure_fernet_key()
