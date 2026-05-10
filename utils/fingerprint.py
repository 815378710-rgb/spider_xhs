# encoding: utf-8
"""
浏览器指纹伪装模块
生成随机但合理的浏览器指纹参数，附加到请求 cookies 中
"""
import random
import hashlib
import time
from loguru import logger


# ── 常用的 Screen 分辨率 ──
_SCREEN_RESOLUTIONS = [
    (1920, 1080), (2560, 1440), (1366, 768), (1536, 864),
    (1440, 900), (1600, 900), (1280, 720), (2560, 1600),
    (1280, 800), (1680, 1050), (1920, 1200), (3840, 2160),
]

# ── 常用的 Platform ──
_PLATFORMS = [
    'Win32', 'MacIntel', 'Linux x86_64',
]

# ── 常用的浏览器版本号 ──
_CHROME_VERSIONS = [
    '147.0.0.0', '146.0.0.0', '145.0.0.0', '144.0.0.0',
    '143.0.0.0', '142.0.0.0', '141.0.0.0', '140.0.0.0',
]

# ── Languages ──
_LANGUAGES = [
    'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'zh-CN,zh;q=0.9,en;q=0.8',
    'zh-CN,zh;q=0.9',
]

# ── Timezone ──
_TIMEZONES = [
    'Asia/Shanghai', 'Asia/Chongqing', 'Asia/Harbin',
]

_COLORS = [
    (24, 24, 24, (24,)),
    (0, 0, 0, (0,)),
    (33, 33, 33, (33,)),
    (48, 48, 48, (48,)),
]

_COLOR_DEPTH = [24, 30, 32]


class BrowserFingerprint:
    """生成一致的浏览器指纹"""

    def __init__(self, seed=None):
        self._seed = seed or int(time.time() * 1000)
        self._rng = random.Random(self._seed)
        # 一次生成，多次使用（保证一致性）
        self._fp = self._generate()

    def _generate(self):
        r = self._rng
        screen_w, screen_h = r.choice(_SCREEN_RESOLUTIONS)
        platform = r.choice(_PLATFORMS)
        chrome_ver = r.choice(_CHROME_VERSIONS)
        lang = r.choice(_LANGUAGES)

        # Canvas fingerprint hash (模拟真实浏览器差异)
        canvas_str = f"{r.randint(10000,99999)}|{screen_w}x{screen_h}|{platform}"
        canvas_hash = hashlib.md5(canvas_str.encode()).hexdigest()[:32]

        # WebGL
        gl_vendor = r.choice(['Google Inc. (NVIDIA)', 'Google Inc. (AMD)', 'Google Inc. (Intel)', 'Google Inc.'])
        gl_renderer = r.choice([
            'ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)',
            'ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)',
            'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)',
            'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)',
            'ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0)',
            'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)',
        ])
        gl_version = r.choice(['WebGL 1.0 (OpenGL ES 2.0 Chromium)', 'WebGL 2.0 (OpenGL ES 3.0 Chromium)'])

        # 字体列表（随机子集，模拟不同系统的字体差异）
        all_fonts = [
            'Arial', 'Arial Black', 'Calibri', 'Cambria', 'Candara',
            'Comic Sans MS', 'Consolas', 'Constantia', 'Corbel',
            'Courier New', 'Georgia', 'Impact', 'Lucida Console',
            'Microsoft Sans Serif', 'Palatino Linotype', 'Segoe UI',
            'Tahoma', 'Times New Roman', 'Trebuchet MS', 'Verdana',
        ]
        num_fonts = r.randint(12, len(all_fonts))
        fonts = sorted(r.sample(all_fonts, num_fonts))

        return {
            'screen_width': screen_w,
            'screen_height': screen_h,
            'screen_avail_width': screen_w - r.randint(0, 40),
            'screen_avail_height': screen_h - r.randint(40, 100),
            'screen_color_depth': r.choice(_COLOR_DEPTH),
            'screen_pixel_depth': r.choice(_COLOR_DEPTH),
            'platform': platform,
            'language': lang,
            'timezone': r.choice(_TIMEZONES),
            'timezone_offset': r.choice([-480, -540, -600, 0, 480, 540]),
            'chrome_version': chrome_ver,
            'canvas_hash': canvas_hash,
            'webgl_vendor': gl_vendor,
            'webgl_renderer': gl_renderer,
            'webgl_version': gl_version,
            'fonts': fonts,
            # 用于 UA 生成
            'ua_platform': 'Windows' if platform == 'Win32' else ('Macintosh' if platform == 'MacIntel' else 'Linux'),
        }

    def get_cookies(self):
        """返回应附加到请求的 cookie 字典"""
        fp = self._fp
        # 小红书使用的指纹 cookie
        return {
            'xsecappid': 'xhs-pc-web',
            'webBuild': '6.7.4',
        }

    def get_web_info_dict(self):
        """返回完整的 webInfo 字典（用于 JS 签名上下文）"""
        fp = self._fp
        return {
            'screen_width': fp['screen_width'],
            'screen_height': fp['screen_height'],
            'screen_avail_width': fp['screen_avail_width'],
            'screen_avail_height': fp['screen_avail_height'],
            'screen_color_depth': fp['screen_color_depth'],
            'screen_pixel_depth': fp['screen_pixel_depth'],
            'platform': fp['platform'],
            'language': fp['language'],
            'timezone': fp['timezone'],
            'timezone_offset': fp['timezone_offset'],
        }

    def get_user_agent(self):
        """生成匹配指纹的 User-Agent"""
        fp = self._fp
        chrome_ver = fp['chrome_version'].split('.')[0]
        # 完整版本号格式: Chrome/147.0.0.0
        return (f"Mozilla/5.0 ({fp['ua_platform']}; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{fp['chrome_version']} Safari/537.36")

    def get_sec_ch_ua(self):
        """返回 sec-ch-ua 头"""
        ver = self._fp['chrome_version'].split('.')[0]
        return f'"Google Chrome";v="{ver}", "Not.A/Brand";v="8", "Chromium";v="{ver}"'

    def get_sec_ch_ua_mobile(self):
        return '?0'

    def get_sec_ch_ua_platform(self):
        return f'"{self._fp["ua_platform"]}"'

    def get_summary(self):
        """返回指纹摘要（用于调试）"""
        fp = self._fp
        return {
            'screen': f"{fp['screen_width']}x{fp['screen_height']}",
            'platform': fp['platform'],
            'chrome': fp['chrome_version'],
            'canvas': fp['canvas_hash'][:16],
            'gl_vendor': fp['webgl_vendor'].split('(')[0] if '(' in fp['webgl_vendor'] else fp['webgl_vendor'],
            'fonts_count': len(fp['fonts']),
            'lang': fp['language'].split(',')[0],
        }


# 全局指纹实例（可随时 recreate）
_fingerprint = BrowserFingerprint()

def get_fingerprint():
    return _fingerprint

def regenerate_fingerprint(seed=None):
    global _fingerprint
    _fingerprint = BrowserFingerprint(seed)
    logger.info(f"[fingerprint] 新指纹已生成: {_fingerprint.get_summary()}")
    return _fingerprint
