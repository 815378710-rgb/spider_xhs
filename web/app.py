"""
土豆小红书助手 - Flask Web 应用
"""
# execjs 补丁在 xhs_utils/xhs_util.py 中统一处理，此处只需确保路径正确
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import random
import threading
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit
from loguru import logger
from dotenv import load_dotenv

from apis.xhs_pc_apis import XHS_Apis
from apis.xhs_pc_login_apis import XHSLoginApi
from utils.rewrite import create_backend, rewrite_note, rewrite_with_debate
from utils.image_processor import process_images

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(_env_path)
logger.info(f"📂 加载 .env: {_env_path} (exists={os.path.exists(_env_path)})")

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# 注册 API 蓝图
from api.pc import pc_bp
from api.creator import creator_bp
from api.pgy import pgy_bp
from api.qianfan import qf_bp

app.register_blueprint(pc_bp)
app.register_blueprint(creator_bp)
app.register_blueprint(pgy_bp)
app.register_blueprint(qf_bp)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'potato-xhs-helper-secret')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 全局配置（持久化到 config/app_config.json，容器重启不丢失）
_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "app_config.json")

def _load_config():
    """从文件加载配置，不存在则用环境变量初始化"""
    defaults = {
        'cookies': os.getenv('COOKIES', ''),
        'llm_provider': os.getenv('LLM_PROVIDER', 'deepseek'),
        'llm_api_key': os.getenv('LLM_API_KEY', ''),
        'llm_model': os.getenv('LLM_MODEL', 'deepseek-v3'),
        'llm_base_url': os.getenv('LLM_BASE_URL', ''),
    }
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            defaults.update(saved)
            logger.info(f"📂 从 {_CONFIG_FILE} 加载配置")
        except Exception as e:
            logger.warning(f"加载配置文件失败，使用默认值: {e}")
    return defaults

def _save_config():
    """将当前 CONFIG 持久化到文件"""
    try:
        os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
        with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(CONFIG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")

CONFIG = _load_config()
logger.info(f"🤖 LLM: provider={CONFIG['llm_provider']}, model={CONFIG['llm_model']}, base_url={CONFIG['llm_base_url']}, key={'✅' if CONFIG['llm_api_key'] else '❌'}")

# ── 持久化存储路径 ──
_CONFIG_DIR = os.path.dirname(_CONFIG_FILE)
_STATS_FILE = os.path.join(_CONFIG_DIR, 'stats.json')
_HISTORY_FILE = os.path.join(_CONFIG_DIR, 'history.json')

# ── 统计数据（从文件加载）──
def _load_stats():
    today = datetime.now().strftime('%Y-%m-%d')
    defaults = {
        'total_processed': 0, 'total_rewritten': 0,
        'today_processed': 0, 'today_rewritten': 0, 'last_date': today,
    }
    if os.path.exists(_STATS_FILE):
        try:
            with open(_STATS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    # 日期轮转
    if defaults['last_date'] != today:
        defaults['today_processed'] = 0
        defaults['today_rewritten'] = 0
        defaults['last_date'] = today
    return defaults

def _save_stats():
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        with open(_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(STATS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存统计数据失败: {e}")

STATS = _load_stats()

# ── 历史记录（从文件加载）──
MAX_HISTORY = 200  # 最多保留 200 条

def _load_history():
    if os.path.exists(_HISTORY_FILE):
        try:
            with open(_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_history():
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        with open(_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(HISTORY[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存历史记录失败: {e}")

HISTORY = _load_history()

def _add_history(record):
    """添加一条历史记录（最多保留 MAX_HISTORY 条）"""
    record['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    HISTORY.insert(0, record)
    if len(HISTORY) > MAX_HISTORY:
        HISTORY[:] = HISTORY[:MAX_HISTORY]
    _save_history()

# ── 关键词监控持久化 ──
_MONITOR_FILE = os.path.join(_CONFIG_DIR, 'monitor.json')

def _load_monitor():
    if os.path.exists(_MONITOR_FILE):
        try:
            with open(_MONITOR_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'keywords': [], 'results': []}

def _save_monitor(data):
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        with open(_MONITOR_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存监控数据失败: {e}")

MONITOR_DATA = _load_monitor()

# ── 断点续传下载状态 ──
_DOWNLOAD_STATE_FILE = os.path.join(_CONFIG_DIR, 'download_state.json')

def _load_download_state():
    if os.path.exists(_DOWNLOAD_STATE_FILE):
        try:
            with open(_DOWNLOAD_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_download_state(state):
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        with open(_DOWNLOAD_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存下载状态失败: {e}")

DOWNLOAD_STATE = _load_download_state()

# 任务状态
TASK_STATUS = {}


def get_llm_backend(model_override=None):
    """获取 LLM 后端实例，支持按次覆盖模型名"""
    try:
        kwargs = {}
        effective_model = model_override or CONFIG['llm_model']
        if effective_model:
            kwargs['model'] = effective_model
        if CONFIG['llm_base_url']:
            kwargs['base_url'] = CONFIG['llm_base_url']
        return create_backend(CONFIG['llm_provider'], CONFIG['llm_api_key'], **kwargs)
    except Exception as e:
        logger.error(f"创建 LLM 后端失败: {e}")
        return None


def update_daily_stats():
    """更新每日统计"""
    today = datetime.now().strftime('%Y-%m-%d')
    if STATS['last_date'] != today:
        STATS['today_processed'] = 0
        STATS['today_rewritten'] = 0
        STATS['last_date'] = today


# ── 图片下载工具 ──────────────────────────────────────────────────────────────
_XHS_IMG_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'Referer': 'https://www.xiaohongshu.com/',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
}

def _resolve_short_url(url):
    """解析小红书短链接（xhslink.com）为完整长链接"""
    if 'xhslink.com' not in url:
        return url
    try:
        import requests as req
        resp = req.head(url, allow_redirects=False, timeout=10,
                        headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'})
        if resp.status_code in (301, 302):
            resolved = resp.headers.get('Location', url)
            logger.info(f"[short_url] {url[:40]} -> {resolved[:80]}")
            return resolved
        # 有些短链服务器直接 GET 跟随
        resp = req.request('GET', url, allow_redirects=True, timeout=10,
                       headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'})
        resolved = resp.url
        if resolved != url:
            logger.info(f"[short_url] {url[:40]} -> {resolved[:80]}")
            return resolved
    except Exception as e:
        logger.warning(f"[short_url] 解析短链接失败: {url} -> {e}")
    return url


def _download_image(url, save_dir=None):
    """下载 XHS CDN 图片到本地，返回本地路径 /static/cached_images/xxx.jpg"""
    import requests as req
    save_dir = save_dir or os.path.join(os.path.dirname(__file__), 'static', 'cached_images')
    os.makedirs(save_dir, exist_ok=True)

    # 如果 URL 已经是本地路径，直接返回
    if url.startswith('/static/'):
        return url

    # 如果文件名含时间戳，避免重复
    filename = f"img_{int(time.time() * 1000)}_{random.randint(1000,9999)}.jpg"
    filepath = os.path.join(save_dir, filename)

    # 多种 headers 尝试下载（CDN 有防盗链）
    header_sets = [
        _XHS_IMG_HEADERS,
        {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://www.xiaohongshu.com/'},
        {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'},
        {},
    ]

    last_error = None
    for headers in header_sets:
        try:
            # 注意：必须用 requests.request() 而非 req.get()，
            # 因为 req.get 已被 monkey-patch 为 _safe_request（注入代理/重试），
            # 图片下载不需要这些增强，直接用 request 绕过。
            resp = req.request('GET', url, headers=headers, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                return f'/static/cached_images/{filename}'
            last_error = f"HTTP {resp.status_code}, size={len(resp.content)}"
        except Exception as e:
            last_error = str(e)

    raise RuntimeError(f"图片下载失败 ({url[:60]}...): {last_error}")


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    return jsonify({
        'cookies_configured': bool(CONFIG['cookies']),
        'cookies': CONFIG.get('cookies', ''),
        'llm_provider': CONFIG['llm_provider'],
        'llm_api_key': CONFIG.get('llm_api_key', ''),
        'llm_model': CONFIG['llm_model'],
        'llm_configured': bool(CONFIG['llm_api_key']),
        'llm_base_url': CONFIG.get('llm_base_url', ''),
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置"""
    data = request.json
    if 'cookies' in data:
        CONFIG['cookies'] = data['cookies']
    if 'llm_provider' in data:
        CONFIG['llm_provider'] = data['llm_provider']
    if 'llm_api_key' in data:
        CONFIG['llm_api_key'] = data['llm_api_key']
    if 'llm_model' in data:
        CONFIG['llm_model'] = data['llm_model']
    if 'llm_base_url' in data:
        CONFIG['llm_base_url'] = data['llm_base_url']
    _save_config()

    # 如果更新了 cookie，自动同步到 cookie 池
    if 'cookies' in data and data['cookies']:
        try:
            from xhs_utils.cookie_util import trans_cookies
            ck = trans_cookies(data['cookies'])
            a1 = ck.get('a1', '')
            if a1:
                _cookie_pool.add_cookie(data['cookies'], username='active', is_valid=True)
        except Exception as e:
            logger.warning(f"同步 cookie 到池失败: {e}")

    return jsonify({'success': True, 'message': '配置已更新'})


# ═══════════════════════════════════════════════════════════════════════════════
# 反爬增强: 频率控制 / 代理池 / 指纹管理
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/anti-crawl/config', methods=['GET'])
def get_anti_crawl_config():
    """获取反爬配置"""
    from utils.rate_limiter import rate_limiter
    from utils.proxy_pool import proxy_pool

    fp_info = {}
    try:
        from utils.fingerprint import get_fingerprint
        fp = get_fingerprint()
        fp_info = fp.get_summary()
    except Exception:
        pass

    return jsonify({
        'success': True,
        'rate_limiter': rate_limiter.get_stats(),
        'proxy_pool': proxy_pool.get_pool_info(),
        'fingerprint': fp_info,
    })


@app.route('/api/anti-crawl/config', methods=['POST'])
def update_anti_crawl_config():
    """更新反爬配置"""
    data = request.json or {}
    from utils.rate_limiter import rate_limiter
    from utils.proxy_pool import proxy_pool

    rl = data.get('rate_limiter', {})
    if rl:
        rate_limiter.update_config(
            min_delay=rl.get('min_delay'),
            max_delay=rl.get('max_delay'),
            max_concurrent=rl.get('max_concurrent'),
        )

    pp = data.get('proxy_pool', {})
    if pp:
        proxy_pool.update_config(
            enabled=pp.get('enabled'),
            proxy_list=pp.get('proxies'),
            check_interval=pp.get('check_interval'),
        )

    return jsonify({'success': True, 'message': '反爬配置已更新'})


@app.route('/api/anti-crawl/fingerprint', methods=['POST'])
def regenerate_fingerprint():
    """重新生成浏览器指纹"""
    from utils.fingerprint import regenerate_fingerprint
    fp = regenerate_fingerprint()
    # 清除 xhs_util 中的指纹缓存，使下一次请求使用新指纹
    import xhs_utils.xhs_util as xu
    xu._FINGERPRINT_CACHE = None
    return jsonify({
        'success': True,
        'message': '新指纹已生成',
        'fingerprint': fp.get_summary(),
    })


@app.route('/api/anti-crawl/proxy/check', methods=['POST'])
def check_proxy_health():
    """检查代理池健康状态"""
    from utils.proxy_pool import proxy_pool
    results = proxy_pool.health_check()
    return jsonify({'success': True, 'results': results})


# ═══════════════════════════════════════════════════════════════════════════════
# 浏览器代理转发队列 — Chrome 扩展从这里拉取请求
# ═══════════════════════════════════════════════════════════════════════════════

_PROXY_QUEUE = []  # [{"request_id": "...", "method": "GET", "url": "...", "headers": {}, "body": "", "created_at": float}]
_PROXY_RESULTS = {}  # request_id -> {"success": bool, "status": int, "data": dict, "error": str}
_PROXY_LOCK = threading.Lock()

@app.route('/api/proxy/pending', methods=['GET'])
def proxy_pending():
    """Chrome 扩展轮询：获取待转发的请求"""
    with _PROXY_LOCK:
        # 清理超过60秒未响应的请求
        now = time.time()
        _PROXY_QUEUE[:] = [r for r in _PROXY_QUEUE if now - r.get('created_at', 0) < 60]
        pending = list(_PROXY_QUEUE[:5])  # 最多同时5个
        _PROXY_QUEUE[:] = _PROXY_QUEUE[5:]
    return jsonify({
        'success': True,
        'requests': [
            {k: v for k, v in r.items() if k != 'created_at'}
            for r in pending
        ],
    })


@app.route('/api/proxy/result', methods=['POST'])
def proxy_result():
    """Chrome 扩展回传请求结果"""
    data = request.json or {}
    request_id = data.get('request_id', '')
    with _PROXY_LOCK:
        _PROXY_RESULTS[request_id] = {
            'success': data.get('success', False),
            'status': data.get('status', 0),
            'data': data.get('data'),
            'error': data.get('error', ''),
        }
    return jsonify({'success': True})


def _enqueue_browser_request(method, url, headers=None, body=None, timeout=30):
    """将请求加入浏览器代理队列，等待 Chrome 扩展转发"""
    import uuid as _uuid
    request_id = str(_uuid.uuid4())[:12]

    with _PROXY_LOCK:
        _PROXY_QUEUE.append({
            'request_id': request_id,
            'method': method,
            'url': url,
            'headers': headers or {},
            'body': body or '',
            'created_at': time.time(),
        })

    # 等待结果
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _PROXY_LOCK:
            result = _PROXY_RESULTS.pop(request_id, None)
        if result is not None:
            return result
        time.sleep(0.3)

    return {'success': False, 'error': 'timeout: 浏览器代理未响应'}


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计数据"""
    update_daily_stats()
    return jsonify(STATS)


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取历史记录"""
    return jsonify({'success': True, 'data': HISTORY, 'total': len(HISTORY)})


@app.route('/api/history', methods=['DELETE'])
def delete_history():
    """清空历史记录"""
    HISTORY.clear()
    _save_history()
    return jsonify({'success': True, 'message': '历史记录已清空'})


@app.route('/api/test-cookie', methods=['POST'])
def test_cookie():
    """测试 Cookie 是否有效"""
    cookies_str = request.json.get('cookies', CONFIG['cookies'])
    if not cookies_str:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})
    
    try:
        xhs = XHS_Apis()
        success, msg, data = xhs.get_user_self_info(cookies_str)
        if success:
            nickname = data.get('data', {}).get('basic_info', {}).get('nickname', '未知')
            return jsonify({'success': True, 'message': f'Cookie 有效，用户: {nickname}'})
        else:
            return jsonify({'success': False, 'message': f'Cookie 无效: {msg}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'测试失败: {str(e)}'})


@app.route('/api/test-ai', methods=['POST'])
def test_ai():
    """测试 AI 模型连接是否正常

    支持两种模式:
    1. POST body 带 provider/api_key/model/base_url → 用临时后端测试（设置面板用）
    2. POST body 为空 → 用全局 CONFIG 测试
    """
    data = request.json or {}

    # 用请求参数覆盖全局配置进行测试
    provider = data.get('provider', CONFIG['llm_provider'])
    api_key = data.get('api_key', CONFIG['llm_api_key'])
    model = data.get('model', CONFIG['llm_model'])
    base_url = data.get('base_url', CONFIG['llm_base_url'])

    if not api_key:
        return jsonify({'success': False, 'message': 'API Key 未配置'})
    try:
        kwargs = {}
        if model:
            kwargs['model'] = model
        if base_url:
            kwargs['base_url'] = base_url
        backend = create_backend(provider, api_key, **kwargs)
        if not backend:
            return jsonify({'success': False, 'message': '创建后端失败'})
        result = backend.chat("你是一个助手", "请回复'连接成功'两个字")
        return jsonify({'success': True, 'message': f'{backend.name} 连接成功！模型回复: {result[:50]}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'{provider}/{model} 连接失败: {str(e)[:100]}'})


@app.route('/api/models', methods=['POST'])
def list_models():
    """从 API 自动获取可用模型列表

    POST body: { provider: "mimo", api_key: "xxx", base_url: "https://..." }
    """
    data = request.json or {}
    provider = data.get('provider', 'mimo')
    api_key = data.get('api_key', '')
    base_url = data.get('base_url', '')

    if not api_key:
        return jsonify({'success': False, 'message': 'API Key 未配置', 'models': []})

    # 根据 provider 确定默认 base_url 和认证头
    if provider == 'mimo':
        default_base = 'https://token-plan-cn.xiaomimimo.com/v1'
        headers = {"api-key": api_key}
    elif provider == 'deepseek':
        default_base = 'https://api.deepseek.com/v1'
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        default_base = base_url or ''
        headers = {"Authorization": f"Bearer {api_key}"}

    target_url = (base_url or default_base).rstrip("/") + "/models"
    if not target_url.startswith("http"):
        return jsonify({'success': False, 'message': 'Base URL 无效', 'models': []})

    try:
        import requests as req
        resp = req.request('GET', target_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        models = []
        for m in data.get("data", []):
            mid = m.get("id", "")
            if mid:
                models.append({"id": mid, "name": mid})

        # 按 provider 做一些排序和默认模型置顶
        if provider == 'mimo':
            # 只保留聊天/推理模型，排除 tts 类
            chat_keywords = ["pro", "omni"]
            preferred = ["mimo-v2.5-pro", "mimo-v2.5", "mimo-v2-pro", "mimo-v2-flash", "mimo-v2-omni"]
            # 标记 display name
            display_names = {
                "mimo-v2.5-pro": "mimo-v2.5-pro (旗舰推理) ⭐",
                "mimo-v2.5": "mimo-v2.5 (全能)",
                "mimo-v2-pro": "mimo-v2-pro (经典推理)",
                "mimo-v2-flash": "mimo-v2-flash (轻量快速)",
                "mimo-v2-omni": "mimo-v2-omni (多模态)",
            }
            models = [m for m in models if not m["id"].endswith("-tts") and "tts" not in m["id"]]
            for m in models:
                if m["id"] in display_names:
                    m["name"] = display_names[m["id"]]
            models.sort(key=lambda x: (
                0 if x["id"] in preferred else 1,
                preferred.index(x["id"]) if x["id"] in preferred else 99,
            ))
        elif provider == 'deepseek':
            preferred = ["deepseek-v3", "deepseek-v4", "deepseek-chat"]
            models.sort(key=lambda x: (
                0 if x["id"] in preferred else 1,
                preferred.index(x["id"]) if x["id"] in preferred else 99,
            ))

        return jsonify({'success': True, 'models': models})
    except Exception as e:
        # API 不支持 /models 端点，返回硬编码列表作为兜底
        fallback = _get_fallback_models(provider)
        return jsonify({
            'success': True,
            'models': fallback,
            'message': f'自动获取失败（{str(e)[:60]}），使用默认列表',
        })


def _get_fallback_models(provider):
    """硬编码的模型兜底列表"""
    if provider == 'mimo':
        return [
            {"id": "mimo-v2-pro", "name": "mimo-v2-pro (旗舰推理)"},
            {"id": "mimo-v2-flash", "name": "mimo-v2-flash (轻量快速)"},
        ]
    elif provider == 'deepseek':
        return [
            {"id": "deepseek-v3", "name": "DeepSeek V3"},
            {"id": "deepseek-v4", "name": "DeepSeek V4"},
        ]
    return []


# ── 扫码登录 API ──────────────────────────────────────────────────────────────

# 存储登录会话
LOGIN_SESSIONS = {}
LOGIN_SESSION_TTL = 300  # 5分钟过期
_LOGIN_SESSION_LAST_CLEANUP = [0]  # mutable container for closure

def _cleanup_login_sessions():
    """清理过期的登录会话，防止内存泄漏"""
    now = time.time()
    if now - _LOGIN_SESSION_LAST_CLEANUP[0] < 60:  # 最多每分钟检查一次
        return
    _LOGIN_SESSION_LAST_CLEANUP[0] = now
    expired = [sid for sid, s in LOGIN_SESSIONS.items() if now - s.get('created_at', 0) > LOGIN_SESSION_TTL]
    for sid in expired:
        LOGIN_SESSIONS.pop(sid, None)
    if expired:
        logger.info(f"[cleanup] 清理 {len(expired)} 个过期登录会话，剩余 {len(LOGIN_SESSIONS)} 个")

# Cookie 池实例
from xhs_utils.xhs_cookie import XhsCookie
_cookie_pool = XhsCookie()


@app.route('/api/login/qrcode', methods=['POST'])
def login_qrcode():
    """获取小红书二维码

    分步处理避免超时：
    1. generate_init_cookies() — 生成初始 Cookie（涉及 sec cookies + gid 网络请求）
    2. generate_qrcode() — 获取二维码
    """
    try:
        _cleanup_login_sessions()
        try:
            import execjs as _ej
            logger.info(f"[DEBUG] execjs Node available: {_ej.get('Node').is_available()}")
        except Exception:
            pass

        # 分步执行，每步单独 try-catch 定位失败点
        login_api = XHSLoginApi()

        try:
            cookies = login_api.generate_init_cookies()
            logger.info(f"[login] init cookies OK, a1={cookies.get('a1', '')[:16]}...")
        except Exception as e:
            logger.error(f"[login] generate_init_cookies 失败: {e}")
            return jsonify({
                'success': False,
                'message': f'生成初始 Cookie 失败（签名/网络错误）: {str(e)[:80]}'
            })

        try:
            success, msg, qr_data = login_api.generate_qrcode(cookies)
        except Exception as e:
            logger.error(f"[login] generate_qrcode 失败: {e}")
            return jsonify({
                'success': False,
                'message': f'获取二维码失败（网络/签名错误）: {str(e)[:80]}'
            })

        if not success:
            return jsonify({'success': False, 'message': f'获取二维码失败: {msg}'})

        session_id = f"login_{int(time.time() * 1000)}"
        LOGIN_SESSIONS[session_id] = {
            'cookies': qr_data['cookies'],
            'qr_id': qr_data['qr_id'],
            'code': qr_data['code'],
            'qr_url': qr_data['qr_url'],
            'login_api': login_api,
            'created_at': time.time(),
        }

        return jsonify({
            'success': True,
            'session_id': session_id,
            'qr_url': qr_data['qr_url'],
        })
    except Exception as e:
        logger.exception(f"获取二维码异常: {e}")
        return jsonify({'success': False, 'message': f'服务器异常: {str(e)[:100]}'})


@app.route('/api/login/qrcode/status', methods=['GET'])
def login_qrcode_status():
    """仅获取二维码状态（不触发登录，用于调试）"""
    return jsonify({
        'success': True,
        'active_sessions': len(LOGIN_SESSIONS),
        'pool_info': _cookie_pool.get_pool_info(),
    })


@app.route('/api/login/check', methods=['POST'])
def login_check():
    """轮询检查扫码状态"""
    data = request.json or {}
    session_id = data.get('session_id', '')

    session = LOGIN_SESSIONS.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': '登录会话不存在或已过期'})

    # 超时检测（5分钟）
    if time.time() - session['created_at'] > 300:
        LOGIN_SESSIONS.pop(session_id, None)
        return jsonify({'success': False, 'message': '二维码已过期，请重新获取'})

    try:
        login_api = session['login_api']
        cookies = session['cookies']
        success, msg, cookies = login_api.check_qrcode_status(
            session['qr_id'], session['code'], cookies
        )
        session['cookies'] = cookies

        logger.info(f"[login_check] check_qrcode_status: success={success}, msg={msg}, "
                     f"cookies keys={list(cookies.keys())}, has_web_session={'web_session' in cookies}")

        if success:
            # 扫码成功，获取用户信息并提取 cookie 字符串
            success2, user_info, cookies = login_api.get_user_info(cookies)
            logger.info(f"[login_check] get_user_info: success={success2}, "
                         f"cookies keys={list(cookies.keys())}, has_web_session={'web_session' in cookies}")

            # 检查关键 Cookie 是否齐全（web_session 是采集 API 必需的）
            if 'web_session' not in cookies:
                logger.warning(f"[login_check] web_session 缺失，尝试额外恢复...")
                # 尝试直接用 cookie 调用 /user/me 看 Set-Cookie 是否返回 web_session
                cookies = login_api._try_get_session_from_page(cookies)
                logger.info(f"[login_check] 恢复后 cookies keys={list(cookies.keys())}, "
                             f"has_web_session={'web_session' in cookies}")

            cookies_str = login_api.cookies_to_str(cookies)

            # 验证 Cookie 是否真正可用（调用 get_user_self_info）
            logger.info(f"[login_check] 验证 cookie 是否可用...")
            verify_ok, verify_msg, _ = XHS_Apis().get_user_self_info(cookies_str)
            logger.info(f"[login_check] 验证结果: ok={verify_ok}, msg={verify_msg}")

            if not verify_ok and 'web_session' not in cookies:
                # Cookie 不可用且无法恢复，报告失败
                logger.error(f"[login_check] Cookie 验证失败且 web_session 缺失: {verify_msg}")
                LOGIN_SESSIONS.pop(session_id, None)
                return jsonify({
                    'success': False,
                    'message': f'登录成功但 Cookie 不完整（缺少 web_session），请重试: {verify_msg[:80]}',
                })

            # 自动保存到配置
            CONFIG['cookies'] = cookies_str
            _save_config()

            # 加入 Cookie 池
            nickname = user_info.get('nickname', '未知') if success2 else '未知'
            _cookie_pool.add_cookie(cookies_str, username=nickname, is_valid=verify_ok)
            logger.info(f"[login] Cookie 已加入池: {nickname}, verified={verify_ok}")

            # 清理会话
            LOGIN_SESSIONS.pop(session_id, None)

            return jsonify({
                'success': True,
                'message': f'登录成功！用户: {nickname}',
                'cookies': cookies_str,
                'user': {'nickname': nickname} if success2 else None,
            })
        else:
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        logger.exception(f"检查扫码状态异常: {e}")
        return jsonify({'success': False, 'message': f'检查状态异常: {str(e)[:80]}'})


@app.route('/api/login/phone/send', methods=['POST'])
def login_phone_send():
    """发送手机验证码"""
    from apis.xhs_pc_login_apis import XHSLoginApi
    data = request.json
    phone = data.get('phone', '').strip()
    if not phone:
        return jsonify({'success': False, 'message': '请输入手机号'})
    try:
        _cleanup_login_sessions()
        login_api = XHSLoginApi()
        cookies = login_api.generate_init_cookies()
        success, msg, _ = login_api.send_phone_code(phone, cookies)
        session_id = f"phone_{int(time.time() * 1000)}"
        LOGIN_SESSIONS[session_id] = {
            'cookies': cookies, 'login_api': login_api,
            'phone': phone, 'type': 'phone', 'created_at': time.time(),
        }
        return jsonify({'success': success, 'message': msg, 'session_id': session_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/login/phone/verify', methods=['POST'])
def login_phone_verify():
    """手机验证码登录"""
    data = request.json
    session_id = data.get('session_id', '')
    code = data.get('code', '').strip()
    logger.info(f"[phone_verify] session_id={session_id}, code={code}")

    session = LOGIN_SESSIONS.get(session_id)
    if not session or session.get('type') != 'phone':
        logger.error(f"[phone_verify] 会话不存在: session_id={session_id}, sessions={list(LOGIN_SESSIONS.keys())}")
        return jsonify({'success': False, 'message': '会话不存在'})
    if time.time() - session['created_at'] > 300:
        LOGIN_SESSIONS.pop(session_id, None)
        return jsonify({'success': False, 'message': '验证码已过期'})

    try:
        login_api = session['login_api']
        init_cookies = session['cookies']
        logger.info(f"[phone_verify] init_cookies keys={list(init_cookies.keys())}, has_a1={'a1' in init_cookies}")

        # Step 1: 验证验证码 + 登录
        success, msg, result = login_api.login_by_phone(
            session['phone'], code, init_cookies
        )
        logger.info(f"[phone_verify] login_by_phone: success={success}, msg={msg}")

        if not success:
            # 登录失败也保存当前 cookies（可能有 sec cookies 等有用的）
            cookies = init_cookies
            cookies_str = login_api.cookies_to_str(cookies)
            logger.warning(f"[phone_verify] 登录失败，但保存 cookies_str={cookies_str[:200]}")
            CONFIG['cookies'] = cookies_str
            _save_config()
            return jsonify({'success': False, 'message': msg})

        # Step 2: 获取用户信息
        cookies = result['cookies']
        logger.info(f"[phone_verify] cookies after login: keys={list(cookies.keys())}")
        s2, user_info, cookies = login_api.get_user_info(cookies)
        logger.info(f"[phone_verify] get_user_info: success={s2}, keys={list(cookies.keys())}")

        # Step 3: 转成字符串并保存
        cookies_str = login_api.cookies_to_str(cookies)
        logger.info(f"[phone_verify] cookies_str={cookies_str[:300]}")

        CONFIG['cookies'] = cookies_str
        _save_config()

        nickname = user_info.get('nickname', '未知') if s2 else '未知'
        _cookie_pool.add_cookie(cookies_str, username=nickname, is_valid=True)
        LOGIN_SESSIONS.pop(session_id, None)
        logger.info(f"[phone_verify] 登录成功! nickname={nickname}")
        return jsonify({'success': True, 'message': f'登录成功！用户: {nickname}', 'cookies': cookies_str})

    except Exception as e:
        logger.exception(f"[phone_verify] 异常: {e}")
        return jsonify({'success': False, 'message': f'登录异常: {str(e)}'})


# ── Cookie 池 API ────────────────────────────────────────────────────────────

@app.route('/api/cookie/pool', methods=['GET'])
def cookie_pool_info():
    """获取 Cookie 池概览（包含当前活跃 Cookie）"""
    info = _cookie_pool.get_pool_info()
    # 把当前活跃 Cookie 也同步显示（如果池中没有的话）
    if CONFIG.get('cookies'):
        from xhs_utils.cookie_util import trans_cookies
        active_a1 = trans_cookies(CONFIG['cookies']).get('a1', '')
        in_pool = any(
            trans_cookies(item.get('cookies_str', '')).get('a1') == active_a1
            for item in _cookie_pool.pool
        )
        if not in_pool and active_a1:
            info['active_cookie'] = {
                'a1': active_a1,
                'is_active': True,
            }
        else:
            info['active_cookie'] = {'a1': active_a1, 'is_active': True}
    return jsonify({'success': True, 'data': info})


@app.route('/api/cookie/pool/validate', methods=['POST'])
def cookie_pool_validate():
    """验证 Cookie 池中所有 Cookie 的有效性"""
    try:
        results = _cookie_pool.validate_all()
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/cookie/pool/auto-update', methods=['POST'])
def cookie_pool_auto_update():
    """自动更新 Cookie 池（验证 + 清理失效）"""
    try:
        results = _cookie_pool.auto_update()
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/cookie/pool/use-best', methods=['POST'])
def cookie_pool_use_best():
    """从 Cookie 池中取最佳 Cookie 并应用到当前配置"""
    data = request.json or {}
    index = data.get('index')
    if index is not None and 0 <= index < len(_cookie_pool.pool):
        CONFIG['cookies'] = _cookie_pool.pool[index]['cookies_str']
        _save_config()
        return jsonify({'success': True, 'message': f'已应用 Cookie [{index}]'})
    best = _cookie_pool.get_best_cookie()
    if not best:
        return jsonify({'success': False, 'message': 'Cookie 池中没有有效 Cookie'})
    CONFIG['cookies'] = best
    _save_config()
    return jsonify({'success': True, 'message': '已应用池中最佳 Cookie', 'cookies': best})


@app.route('/api/cookie/pool/add', methods=['POST'])
def cookie_pool_add():
    """手动添加 Cookie 到池中"""
    data = request.json or {}
    cookies_str = data.get('cookies', '').strip()
    if not cookies_str:
        return jsonify({'success': False, 'message': '请输入 Cookie'})
    _cookie_pool.add_cookie(cookies_str, username=data.get('username', '手动添加'), is_valid=True)
    return jsonify({'success': True, 'message': f'已添加到 Cookie 池（共 {len(_cookie_pool.pool)} 条）'})


@app.route('/api/cookie/pool/remove', methods=['POST'])
def cookie_pool_remove():
    """从 Cookie 池中移除指定 Cookie"""
    data = request.json or {}
    index = data.get('index')
    a1 = data.get('a1')
    if index is None and not a1:
        return jsonify({'success': False, 'message': '请指定 index 或 a1'})
    _cookie_pool.remove_cookie(index=index, a1=a1)
    return jsonify({'success': True, 'message': f'已移除（剩余 {len(_cookie_pool.pool)} 条）'})


@app.route('/api/note/collect', methods=['POST'])
def collect_note():
    """采集笔记"""
    data = request.json
    note_url = data.get('url', '').strip()
    if not note_url:
        return jsonify({'success': False, 'message': '请输入笔记链接'})

    # 解析短链接
    note_url = _resolve_short_url(note_url)

    if not CONFIG['cookies']:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})
    
    try:
        time.sleep(random.uniform(0.5, 1.5))  # 防限流
        xhs = XHS_Apis()
        success, msg, note_info = xhs.get_note_info(note_url, CONFIG['cookies'])
        
        if not success:
            return jsonify({'success': False, 'message': f'采集失败: {msg}'})

        # 安全获取 note 数据（API 可能返回空 data）
        items = note_info.get('data', {}).get('items', [])
        if not items:
            # 尝试另一种数据结构（有些笔记返回 note_card 在顶层）
            note_card = note_info.get('data', {}).get('note_card', None)
            if not note_card:
                return jsonify({'success': False, 'message': f'采集失败: 笔记数据为空，请检查链接是否有效'})
            note = note_info['data']
        else:
            note = items[0]
            note_card = note['note_card']
        
        # 提取图片并下载到本地（CDN 403 防盗链，必须本地缓存）
        images = []
        image_list = note_card.get('image_list', [])
        logger.info(f"[collect_note] 图片列表: {len(image_list)} 张")
        for idx, img in enumerate(image_list):
            info_list = img.get('info_list', [])
            # 尝试多种索引: 优先 info_list[1]（大图），fallback info_list[0]
            cdn_url = None
            if len(info_list) > 1:
                cdn_url = info_list[1].get('url', '')
            elif len(info_list) > 0:
                cdn_url = info_list[0].get('url', '')

            if not cdn_url:
                # 尝试 url_default / url_pre 字段
                cdn_url = img.get('url_default', '') or img.get('url_pre', '') or ''

            if cdn_url:
                try:
                    local_path = _download_image(cdn_url)
                    images.append(local_path)
                    logger.info(f"[collect_note] 图片 {idx+1} 下载成功: {local_path}")
                except Exception as e:
                    logger.warning(f"[collect_note] 图片 {idx+1} 下载失败: {cdn_url[:60]} -> {e}")
                    images.append(cdn_url)  # fallback to CDN URL
            else:
                logger.warning(f"[collect_note] 图片 {idx+1} 无可用URL, keys={list(img.keys())}")

        logger.info(f"[collect_note] 最终图片数: {len(images)}")
        
        result = {
            'note_id': note.get('id', ''),
            'title': note_card.get('title', ''),
            'desc': note_card.get('desc', ''),
            'images': images,
            'author': note_card.get('user', {}).get('nickname', ''),
            'likes': note_card.get('interact_info', {}).get('liked_count', 0),
            'collects': note_card.get('interact_info', {}).get('collected_count', 0),
            'comments': note_card.get('interact_info', {}).get('comment_count', 0),
        }
        
        update_daily_stats()
        STATS['today_processed'] += 1
        STATS['total_processed'] += 1
        
        return jsonify({'success': True, 'data': result})
        
    except Exception as e:
        logger.exception(f"采集笔记异常: {e}")
        return jsonify({'success': False, 'message': f'采集异常: {str(e)}'})


@app.route('/api/note/rewrite', methods=['POST'])
def rewrite_note_api():
    """AI 改写笔记"""
    data = request.json
    title = data.get('title', '')
    desc = data.get('desc', '')
    style = data.get('style', '保持原风格')
    model = data.get('model', '')
    
    if not title and not desc:
        return jsonify({'success': False, 'message': '没有可改写的内容'})
    
    if not CONFIG['llm_api_key']:
        return jsonify({'success': False, 'message': 'AI API Key 未配置'})
    
    try:
        backend = get_llm_backend(model_override=model or None)
        if not backend:
            return jsonify({'success': False, 'message': '创建 AI 后端失败'})
        
        result = rewrite_note(title, desc, backend, style=style)
        
        update_daily_stats()
        STATS['today_rewritten'] += 1
        STATS['total_rewritten'] += 1
        
        return jsonify({'success': True, 'data': result})
        
    except Exception as e:
        logger.exception(f"AI 改写异常: {e}")
        return jsonify({'success': False, 'message': f'改写异常: {str(e)}'})


@app.route('/api/note/rewrite_smart', methods=['POST'])
def rewrite_smart_api():
    """智能改写（支持Agent辩论）"""
    data = request.json
    title = data.get('title', '')
    desc = data.get('desc', '')
    style = data.get('style', '保持原风格')
    ratio = int(data.get('ratio', 50))
    model = data.get('model', '')
    debate = data.get('debate', True)

    if not title and not desc:
        return jsonify({'success': False, 'message': '没有可改写的内容'})

    if not CONFIG['llm_api_key']:
        return jsonify({'success': False, 'message': 'AI API Key 未配置'})

    try:
        backend = get_llm_backend(model_override=model or None)
        if not backend:
            return jsonify({'success': False, 'message': '创建 AI 后端失败'})

        if debate:
            result = rewrite_with_debate(title, desc, backend, style=style, ratio=ratio)
        else:
            # 单次改写，包装成辩论格式
            single = rewrite_note(title, desc, backend, style=style, ratio=ratio)
            result = {
                "winner": single,
                "alternatives": [],
                "scores": {},
                "reasoning": "单次改写模式，未启用辩论",
                "all_versions": [single],
            }

        update_daily_stats()
        STATS['today_rewritten'] += 1
        STATS['total_rewritten'] += 1

        return jsonify({'success': True, 'data': result})

    except Exception as e:
        logger.exception(f"智能改写异常: {e}")
        return jsonify({'success': False, 'message': f'改写异常: {str(e)}'})


@app.route('/api/note/batch_rewrite', methods=['POST'])
def batch_rewrite_api():
    """批量改写笔记（来自批量采集的选中结果）"""
    data = request.json or {}
    notes = data.get('notes', [])  # [{title, desc}, ...]
    style = data.get('style', '保持原风格')
    ratio = int(data.get('ratio', 50))
    debate = data.get('debate', True)
    model = data.get('model', '')

    if not notes:
        return jsonify({'success': False, 'message': '没有可改写的笔记'})
    if len(notes) > 20:
        return jsonify({'success': False, 'message': '单次最多改写 20 条笔记'})
    if not CONFIG['llm_api_key']:
        return jsonify({'success': False, 'message': 'AI API Key 未配置'})

    try:
        backend = get_llm_backend(model_override=model or None)
        if not backend:
            return jsonify({'success': False, 'message': '创建 AI 后端失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'AI 后端初始化失败: {str(e)}'})

    task_id = f'batch_rw_{int(time.time())}'
    results = []
    total = len(notes)
    success_count = 0
    fail_count = 0

    for i, note in enumerate(notes):
        title = note.get('title', '')
        desc = note.get('desc', '')
        original_title = title

        # 推送进度
        socketio.emit('batch_rewrite_progress', {
            'task_id': task_id,
            'current': i + 1,
            'total': total,
            'status': 'rewriting',
            'message': f'正在改写 {i+1}/{total}: {title[:20]}...',
        })

        try:
            time.sleep(random.uniform(0.5, 1.5))  # 防 API 限流

            if debate:
                result = rewrite_with_debate(title, desc, backend, style=style, ratio=ratio)
                # 取 winner 作为最终结果
                winner = result.get('winner', {})
                rewritten = {
                    'title': winner.get('title', ''),
                    'desc': winner.get('desc', ''),
                }
                scores = result.get('scores', {})
                reasoning = result.get('reasoning', '')
                all_versions = result.get('all_versions', [])
            else:
                single = rewrite_note(title, desc, backend, style=style, ratio=ratio)
                rewritten = {
                    'title': single.get('title', ''),
                    'desc': single.get('desc', ''),
                }
                scores = {}
                reasoning = '单次改写模式'
                all_versions = [single]

            results.append({
                'original_title': original_title,
                'original_desc': desc,
                'rewritten': rewritten,
                'scores': scores,
                'reasoning': reasoning,
                'all_versions': all_versions,
                'success': True,
            })
            success_count += 1

            # 推送单条完成
            socketio.emit('batch_rewrite_progress', {
                'task_id': task_id,
                'current': i + 1,
                'total': total,
                'status': 'done',
                'message': f'✅ {i+1}/{total} 改写完成: {rewritten["title"][:20]}...',
            })

        except Exception as e:
            logger.exception(f"[batch_rewrite] 第{i+1}条改写失败: {e}")
            results.append({
                'original_title': original_title,
                'original_desc': desc,
                'rewritten': {'title': '', 'desc': ''},
                'scores': {},
                'reasoning': '',
                'all_versions': [],
                'success': False,
                'error': str(e),
            })
            fail_count += 1

            socketio.emit('batch_rewrite_progress', {
                'task_id': task_id,
                'current': i + 1,
                'total': total,
                'status': 'error',
                'message': f'❌ {i+1}/{total} 改写失败: {str(e)[:50]}',
            })

    # 更新统计
    update_daily_stats()
    STATS['today_rewritten'] += success_count
    STATS['total_rewritten'] += success_count

    # 推送全部完成
    socketio.emit('batch_rewrite_progress', {
        'task_id': task_id,
        'current': total,
        'total': total,
        'status': 'all_done',
        'message': f'批量改写完成: {success_count} 成功, {fail_count} 失败',
    })

    return jsonify({
        'success': True,
        'data': results,
        'summary': {
            'total': total,
            'success': success_count,
            'failed': fail_count,
        },
        'message': f'批量改写完成: {success_count}/{total} 成功',
    })


@app.route('/api/images/proxy', methods=['GET'])
def image_proxy():
    """代理下载小红书 CDN 图片，绕过 Referer 防盗链"""
    url = request.args.get('url', '')
    if not url or not url.startswith('http'):
        return 'Bad Request', 400

    import requests as req
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
            'Referer': 'https://www.xiaohongshu.com/',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        }
        resp = req.request('GET', url, headers=headers, timeout=20, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get('Content-Type', 'image/jpeg')
        from flask import Response as FlaskResponse
        return FlaskResponse(resp.iter_content(chunk_size=8192), content_type=content_type)
    except Exception as e:
        logger.warning(f"图片代理失败: {url[:80]} -> {e}")
        return 'Image fetch failed', 502


@app.route('/api/images/process', methods=['POST'])
def process_images_api():
    """图片防重处理"""
    data = request.json
    image_paths = data.get('urls', [])
    level = data.get('level', 'medium')

    if not image_paths:
        return jsonify({'success': False, 'message': '没有图片需要处理'})

    processed = []
    errors = []

    for i, img_path in enumerate(image_paths):
        try:
            # img_path 可能是 /static/cached_images/xxx.jpg 或 CDN URL
            if img_path.startswith('/static/'):
                fs_path = os.path.join(os.path.dirname(__file__), img_path.lstrip('/'))
                with open(fs_path, 'rb') as f:
                    img_bytes = f.read()
            else:
                # Fallback: 尝试下载（使用多套 headers 尝试，和 _download_image 一致）
                import requests as req
                header_sets = [
                    _XHS_IMG_HEADERS,
                    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://www.xiaohongshu.com/'},
                    {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'},
                ]
                img_bytes = None
                for dl_headers in header_sets:
                    try:
                        resp = req.request('GET', img_path, headers=dl_headers, timeout=20)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            img_bytes = resp.content
                            break
                    except Exception:
                        continue
                if img_bytes is None:
                    raise ValueError("CDN 图片下载失败 (HTTP headers 全部失败)")

            if not img_bytes or len(img_bytes) < 100:
                raise ValueError(f"图片数据无效 (size={len(img_bytes) if img_bytes else 0})")

            # 防重处理
            from utils.image_processor import process_image
            processed_bytes = process_image(img_bytes, level)

            # 保存到临时目录
            output_dir = os.path.join(os.path.dirname(__file__), 'static', 'processed')
            os.makedirs(output_dir, exist_ok=True)

            filename = f"processed_{int(time.time())}_{i}.jpg"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'wb') as f:
                f.write(processed_bytes)

            processed.append({
                'original': img_path,
                'processed': f'/static/processed/{filename}',
                'filename': filename,
                'index': i,
            })

        except Exception as e:
            logger.warning(f"[process_images] 图片 {i+1} 处理失败: {img_path[:60]} -> {e}")
            errors.append(f"图片 {i+1}: {str(e)}")
            # 失败时也占位，保证 processed 长度和 image_paths 一致
            processed.append({
                'original': img_path,
                'processed': None,
                'filename': None,
                'index': i,
                'error': str(e),
            })
    
    return jsonify({
        'success': len(processed) > 0,
        'data': processed,
        'errors': errors,
        'message': f'处理完成 {len(processed)}/{len(image_paths)} 张',
    })


@app.route('/api/batch/search', methods=['POST'])
def batch_search():
    """批量搜索笔记"""
    data = request.json
    keyword = data.get('keyword', '').strip()
    count = data.get('count', 10)
    sort_type = data.get('sort_type', 0)
    note_type = data.get('note_type', 0)
    
    if not keyword:
        return jsonify({'success': False, 'message': '请输入搜索关键词'})
    
    if not CONFIG['cookies']:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})
    
    try:
        time.sleep(random.uniform(0.5, 1.5))  # 防限流
        xhs = XHS_Apis()
        success, msg, notes = xhs.search_some_note(
            keyword, count, CONFIG['cookies'],
            sort_type_choice=sort_type,
            note_type=note_type
        )
        
        if not success:
            return jsonify({'success': False, 'message': f'搜索失败: {msg}'})
        
        # 过滤出笔记类型，数据从 note_card 里提取
        note_list = []
        for note in notes:
            # 兼容不同 API 版本：有时 model_type='note'，有时没有此字段但有 note_card
            nc = note.get('note_card', {})
            model_type = note.get('model_type', '')
            nc_type = nc.get('type', '')

            # 跳过明显不是笔记的条目（如广告、用户卡片等）
            if model_type not in ('note', '', None) and model_type != 'note':
                # 如果有 note_card 内容，仍然尝试解析
                if not nc:
                    continue

            # 提取封面图 - 多种字段兼容
            cover = nc.get('cover', {})
            cover_url = ''
            # 尝试 info_list
            cover_info = cover.get('info_list', [])
            if cover_info:
                cover_url = cover_info[0].get('url', '') if cover_info else ''
            # 尝试 url_default / url_pre
            if not cover_url:
                cover_url = cover.get('url_default', '') or cover.get('url_pre', '')
            # 尝试 image_list（有些格式把封面放在 image_list 里）
            if not cover_url:
                img_list = nc.get('image_list', [])
                if img_list:
                    first_img = img_list[0]
                    img_info = first_img.get('info_list', [])
                    if img_info:
                        cover_url = img_info[0].get('url', '')
                    else:
                        cover_url = first_img.get('url_default', '') or first_img.get('url_pre', '')

            # 提取交互数据 - 兼容字符串和数字
            interact = nc.get('interact_info', {})
            liked = interact.get('liked_count', '0')
            liked_text = str(liked) if not isinstance(liked, str) else liked

            # 提取类型
            note_type = nc.get('type', '') or nc_type or model_type or ''
            if note_type not in ('video', 'normal', '图文', '视频'):
                # 根据是否视频判断
                video_info = nc.get('video', {})
                note_type = 'video' if video_info else 'normal'

            # 提取标题 - 搜索API用 display_title，详情API用 title
            title = nc.get('title', '') or nc.get('display_title', '') or note.get('display_title', '') or ''
            if not title:
                # 从 desc 截取
                desc_raw = nc.get('desc', '') or ''
                title = desc_raw[:30] or '(无标题)'

            # 提取作者
            user_info = nc.get('user', {})
            author = user_info.get('nickname', '') or user_info.get('nick_name', '') or '未知'

            # 提取 xsec_token
            xsec = note.get('xsec_token', '') or nc.get('xsec_token', '') or ''

            note_list.append({
                'id': note.get('id', '') or nc.get('note_id', ''),
                'title': title,
                'desc': (nc.get('desc', '') or '')[:80],
                'author': author,
                'likes': liked_text,
                'type': note_type,
                'cover': cover_url,
                'xsec_token': xsec,
            })
        
        return jsonify({'success': True, 'data': note_list})
        
    except Exception as e:
        logger.exception(f"搜索异常: {e}")
        return jsonify({'success': False, 'message': f'搜索异常: {str(e)}'})


@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    logger.info(f"客户端连接: {request.sid}")
    emit('connected', {'message': '连接成功'})


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    logger.info(f"客户端断开: {request.sid}")


@socketio.on('start_task')
def handle_start_task(data):
    """处理任务（带进度推送）"""
    task_type = data.get('type')
    task_id = f"task_{int(time.time() * 1000)}"
    
    TASK_STATUS[task_id] = {'status': 'running', 'progress': 0}
    
    def run_task():
        try:
            if task_type == 'full_process':
                # 完整流程：采集 → 改写 → 图片处理
                url = _resolve_short_url(data.get('url', ''))
                style = data.get('style', '保持原风格')
                ratio = int(data.get('ratio', 50))
                debate = data.get('debate', True)
                model_override = data.get('model', '')
                image_level = data.get('image_level', 'medium')
                
                # Step 1: 采集（加入随机间隔防限流）
                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'collect',
                    'message': '正在采集笔记...',
                    'progress': 10,
                })

                time.sleep(random.uniform(1.0, 2.0))  # 防限流
                xhs = XHS_Apis()
                success, msg, note_info = xhs.get_note_info(url, CONFIG['cookies'])
                
                if not success:
                    socketio.emit('task_error', {'task_id': task_id, 'message': f'采集失败: {msg}'})
                    return

                items = note_info.get('data', {}).get('items', [])
                if items:
                    note = items[0]['note_card']
                else:
                    note = note_info.get('data', {}).get('note_card', {})
                    if not note:
                        socketio.emit('task_error', {'task_id': task_id, 'message': '采集失败: 笔记数据为空'})
                        return
                title = note.get('title', '')
                desc = note.get('desc', '')

                # 提取图片 URL（多种 fallback）
                raw_images = []
                image_list = note.get('image_list', [])
                logger.info(f"[task] 图片列表: {len(image_list)} 张")
                for img in image_list:
                    info_list = img.get('info_list', [])
                    cdn_url = None
                    if len(info_list) > 1:
                        cdn_url = info_list[1].get('url', '')
                    elif len(info_list) > 0:
                        cdn_url = info_list[0].get('url', '')
                    if not cdn_url:
                        cdn_url = img.get('url_default', '') or img.get('url_pre', '') or ''
                    if cdn_url:
                        raw_images.append(cdn_url)
                    else:
                        logger.warning(f"[task] 图片无可用URL, keys={list(img.keys())}")
                logger.info(f"[task] 提取到 {len(raw_images)} 张图片URL")

                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'collect_done',
                    'message': f'采集成功: {title[:20]}...',
                    'progress': 25,
                    'data': {'title': title, 'desc': desc, 'images': raw_images},
                })

                # 下载原图到本地（CDN 有防盗链）
                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'images',
                    'message': f'正在下载 {len(raw_images)} 张原图...',
                    'progress': 30,
                })
                images = []
                for i, img_url in enumerate(raw_images):
                    try:
                        local_path = _download_image(img_url)
                        images.append(local_path)
                    except Exception as e:
                        logger.warning(f"下载原图失败: {img_url[:60]} -> {e}")
                    socketio.emit('task_progress', {
                        'task_id': task_id,
                        'step': 'images',
                        'message': f'下载原图 {i+1}/{len(raw_images)}',
                        'progress': 30 + int(10 * (i + 1) / max(len(raw_images), 1)),
                    })

                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'collect_done',
                    'message': f'下载完成，共 {len(images)} 张',
                    'progress': 40,
                    'data': {'title': title, 'desc': desc, 'images': images},
                })

                # Step 2: AI 改写（支持辩论模式）
                backend = get_llm_backend(model_override=model_override or None)

                if debate:
                    # Agent 辩论模式
                    socketio.emit('task_progress', {
                        'task_id': task_id,
                        'step': 'debate_start',
                        'message': '🤖 启动 Agent 辩论模式...',
                        'progress': 40,
                    })

                    # 通知前端各Agent开始
                    for key in ['A', 'B', 'C']:
                        from utils.rewrite import AGENT_PROFILES
                        profile = AGENT_PROFILES[key]
                        socketio.emit('task_progress', {
                            'task_id': task_id,
                            'step': 'agent_running',
                            'message': f"{profile['emoji']} {profile['name']} 正在改写...",
                            'progress': 42,
                            'agent': key,
                        })

                    socketio.emit('task_progress', {
                        'task_id': task_id,
                        'step': 'rewrite',
                        'message': '🤖 3个Agent并行改写中...',
                        'progress': 45,
                    })

                    debate_result = rewrite_with_debate(title, desc, backend, style=style, ratio=ratio)
                    _debate_result = debate_result
                    result = debate_result['winner']

                    # 通知前端辩论结果
                    socketio.emit('task_progress', {
                        'task_id': task_id,
                        'step': 'debate_result',
                        'message': f"评审完成！最优方案: {result.get('agent_emoji','')} {result.get('agent_name','')}",
                        'progress': 58,
                        'debate_result': {
                            'winner_agent': result.get('agent', ''),
                            'winner_name': result.get('agent_name', ''),
                            'winner_emoji': result.get('agent_emoji', ''),
                            'scores': debate_result.get('scores', {}),
                            'reasoning': debate_result.get('reasoning', ''),
                            'all_versions': debate_result.get('all_versions', []),
                        },
                    })

                    socketio.emit('task_progress', {
                        'task_id': task_id,
                        'step': 'rewrite_done',
                        'message': f"辩论完成，最优方案: {result.get('agent_name','')}",
                        'progress': 60,
                        'data': result,
                    })
                else:
                    # 普通改写模式
                    socketio.emit('task_progress', {
                        'task_id': task_id,
                        'step': 'rewrite',
                        'message': f'正在 AI 改写... (风格:{style} 比例:{ratio}%)',
                        'progress': 40,
                    })

                    result = rewrite_note(title, desc, backend, style=style, ratio=ratio)

                    socketio.emit('task_progress', {
                        'task_id': task_id,
                        'step': 'rewrite_done',
                        'message': '改写完成',
                        'progress': 60,
                        'data': result,
                    })
                
                # Step 3: 图片处理（从本地读取，不再下载）
                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'images',
                    'message': f'正在处理 {len(images)} 张图片...',
                    'progress': 65,
                })

                processed_images = []
                for i, img_path in enumerate(images):
                    try:
                        from utils.image_processor import process_image
                        # img_path 是 /static/cached_images/xxx.jpg，需要映射到文件系统路径
                        fs_path = os.path.join(os.path.dirname(__file__), img_path.lstrip('/'))
                        with open(fs_path, 'rb') as f:
                            img_bytes = f.read()
                        processed_bytes = process_image(img_bytes, image_level)

                        output_dir = os.path.join(os.path.dirname(__file__), 'static', 'processed')
                        os.makedirs(output_dir, exist_ok=True)
                        filename = f"processed_{int(time.time())}_{i}.jpg"
                        filepath = os.path.join(output_dir, filename)

                        with open(filepath, 'wb') as f:
                            f.write(processed_bytes)

                        processed_images.append(f'/static/processed/{filename}')

                        socketio.emit('task_progress', {
                            'task_id': task_id,
                            'step': 'images',
                            'message': f'图片处理中 {i+1}/{len(images)}',
                            'progress': 65 + int(25 * (i + 1) / max(len(images), 1)),
                        })
                    except Exception as e:
                        logger.warning(f"图片处理失败: {e}")
                
                # 完成
                complete_data = {
                    'original': {'title': title, 'desc': desc},
                    'rewritten': result,
                    'images_original': images,
                    'images_processed': processed_images,
                }
                # 如果是辩论模式，附带辩论结果
                debate_result_data = locals().get('_debate_result', None)
                if debate_result_data:
                    complete_data['debate'] = debate_result_data

                socketio.emit('task_complete', {
                    'task_id': task_id,
                    'data': complete_data,
                })

                update_daily_stats()
                STATS['today_processed'] += 1
                STATS['today_rewritten'] += 1
                STATS['total_processed'] += 1
                STATS['total_rewritten'] += 1
                _save_stats()

                # 记录到历史
                _add_history({
                    'type': 'rewrite',
                    'title': title,
                    'desc': desc,
                    'rewritten_title': result.get('title', ''),
                    'rewritten_desc': result.get('desc', ''),
                    'images_count': len(processed_images),
                    'style': style,
                    'model': model_override or CONFIG['llm_model'],
                    'url': url,
                })
                
        except Exception as e:
            logger.exception(f"任务执行异常: {e}")
            socketio.emit('task_error', {'task_id': task_id, 'message': str(e)})
        finally:
            TASK_STATUS[task_id]['status'] = 'done'
    
    # 后台执行任务
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()
    
    emit('task_started', {'task_id': task_id})


@app.route('/api/cookie/collect', methods=['POST'])
def cookie_collect():
    """接收 Chrome 插件发送的 Cookie"""
    data = request.json or {}
    cookies_str = data.get('cookies', '').strip()
    source = data.get('source', 'unknown')

    if not cookies_str:
        return jsonify({'success': False, 'message': '未收到 Cookie 数据'})

    # 验证 Cookie
    try:
        xhs = XHS_Apis()
        success, msg, user_info = xhs.get_user_self_info(cookies_str)
        nickname = '未知'
        is_valid = False
        if success:
            nickname = user_info.get('data', {}).get('basic_info', {}).get('nickname', '未知')
            is_valid = True
        else:
            logger.warning(f"[cookie_collect] Cookie 验证失败: {msg}")
    except Exception as e:
        logger.error(f"[cookie_collect] 验证异常: {e}")
        nickname = '未知'
        is_valid = False

    # 保存到配置
    CONFIG['cookies'] = cookies_str
    _save_config()

    # 加入 Cookie 池
    _cookie_pool.add_cookie(cookies_str, username=nickname, is_valid=is_valid)

    logger.info(f"[cookie_collect] 从 {source} 采集 Cookie，用户: {nickname}, 有效: {is_valid}")
    return jsonify({
        'success': True,
        'message': f'Cookie 已采集！用户: {nickname}' + (' (验证通过)' if is_valid else ' (验证未通过，但已保存)'),
        'nickname': nickname,
        'is_valid': is_valid,
    })


@app.route('/api/model/switch', methods=['POST'])
def model_switch():
    """快捷切换 AI 模型"""
    data = request.json or {}
    model = data.get('model', '').strip()
    if not model:
        return jsonify({'success': False, 'message': '请选择模型'})

    CONFIG['llm_model'] = model
    _save_config()
    logger.info(f"[model_switch] 切换模型到: {model}")
    return jsonify({'success': True, 'message': f'模型已切换为 {model}', 'model': model})


@app.route('/api/cookie/pool/detail', methods=['GET'])
def cookie_pool_detail():
    """获取 Cookie 池中某个 Cookie 的详细信息"""
    index = request.args.get('index', type=int)
    if index is None or index < 0 or index >= len(_cookie_pool.pool):
        return jsonify({'success': False, 'message': '无效索引'})

    item = _cookie_pool.pool[index]
    from xhs_utils.cookie_util import trans_cookies
    ck = trans_cookies(item.get('cookies_str', ''))
    return jsonify({
        'success': True,
        'data': {
            'index': index,
            'username': item.get('username', '未知'),
            'is_valid': item.get('is_valid', False),
            'fetch_date': item.get('fetch_date', ''),
            'last_check': item.get('last_check', ''),
            'a1': ck.get('a1', '')[:12] + '...' if ck.get('a1') else '(无)',
            'web_session': '✅' if ck.get('web_session') else '❌',
            'cookie_keys': list(ck.keys()),
        }
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 功能 1: 关键词监控 + AI 情报分析
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/monitor/keywords', methods=['GET'])
def monitor_keywords():
    """获取所有监控关键词"""
    return jsonify({'success': True, 'data': MONITOR_DATA.get('keywords', [])})


@app.route('/api/monitor/keywords', methods=['POST'])
def monitor_add_keyword():
    """添加监控关键词"""
    data = request.json or {}
    keyword = data.get('keyword', '').strip()
    interval = data.get('interval', 60)  # 分钟
    sort_type = data.get('sort_type', 0)
    note_type = data.get('note_type', 0)

    if not keyword:
        return jsonify({'success': False, 'message': '请输入关键词'})

    # 去重
    for kw in MONITOR_DATA.get('keywords', []):
        if kw['keyword'] == keyword:
            return jsonify({'success': False, 'message': '该关键词已在监控列表中'})

    kw_item = {
        'id': f"kw_{int(time.time() * 1000)}",
        'keyword': keyword,
        'interval': interval,
        'sort_type': sort_type,
        'note_type': note_type,
        'enabled': True,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'last_check': None,
        'total_found': 0,
    }
    MONITOR_DATA.setdefault('keywords', []).append(kw_item)
    _save_monitor(MONITOR_DATA)
    return jsonify({'success': True, 'message': f'已添加监控: {keyword}', 'data': kw_item})


@app.route('/api/monitor/keywords/<kw_id>', methods=['DELETE'])
def monitor_delete_keyword(kw_id):
    """删除监控关键词"""
    kws = MONITOR_DATA.get('keywords', [])
    for i, kw in enumerate(kws):
        if kw['id'] == kw_id:
            kws.pop(i)
            _save_monitor(MONITOR_DATA)
            return jsonify({'success': True, 'message': '已删除'})
    return jsonify({'success': False, 'message': '未找到该关键词'})


@app.route('/api/monitor/keywords/<kw_id>/toggle', methods=['POST'])
def monitor_toggle_keyword(kw_id):
    """启用/禁用监控关键词"""
    for kw in MONITOR_DATA.get('keywords', []):
        if kw['id'] == kw_id:
            kw['enabled'] = not kw.get('enabled', True)
            _save_monitor(MONITOR_DATA)
            return jsonify({'success': True, 'enabled': kw['enabled']})
    return jsonify({'success': False, 'message': '未找到该关键词'})


@app.route('/api/monitor/check', methods=['POST'])
def monitor_check():
    """手动触发一次关键词监控检查"""
    data = request.json or {}
    kw_id = data.get('keyword_id')

    if not CONFIG['cookies']:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})

    targets = []
    if kw_id:
        for kw in MONITOR_DATA.get('keywords', []):
            if kw['id'] == kw_id:
                targets = [kw]
                break
    else:
        targets = [kw for kw in MONITOR_DATA.get('keywords', []) if kw.get('enabled', True)]

    if not targets:
        return jsonify({'success': False, 'message': '没有启用的监控关键词'})

    xhs = XHS_Apis()
    all_new = []

    for kw in targets:
        try:
            time.sleep(random.uniform(1.0, 2.5))
            success, msg, notes = xhs.search_some_note(
                kw['keyword'], 20, CONFIG['cookies'],
                sort_type_choice=kw.get('sort_type', 0),
                note_type=kw.get('note_type', 0),
            )
            if not success:
                logger.warning(f"[monitor] 搜索 '{kw['keyword']}' 失败: {msg}")
                continue

            # 去重：只保留新笔记
            seen_ids = set(r['note_id'] for r in MONITOR_DATA.get('results', []) if r.get('keyword') == kw['keyword'])
            new_notes = []
            for note in notes:
                note_id = note.get('id', '')
                if note_id and note_id not in seen_ids:
                    nc = note.get('note_card', {})
                    interact = nc.get('interact_info', {})
                    liked = interact.get('liked_count', '0')
                    comment = interact.get('comment_count', '0')
                    collect = interact.get('collected_count', '0')
                    new_notes.append({
                        'note_id': note_id,
                        'keyword': kw['keyword'],
                        'title': nc.get('title', '') or nc.get('display_title', '') or note.get('display_title', '') or '(无标题)',
                        'desc': (nc.get('desc', '') or '')[:200],
                        'author': nc.get('user', {}).get('nickname', ''),
                        'author_id': nc.get('user', {}).get('user_id', ''),
                        'liked_count': liked,
                        'comment_count': comment,
                        'collected_count': collect,
                        'type': nc.get('type', ''),
                        'xsec_token': note.get('xsec_token', ''),
                        'found_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })

            all_new.extend(new_notes)
            kw['last_check'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            kw['total_found'] = kw.get('total_found', 0) + len(new_notes)
        except Exception as e:
            logger.exception(f"[monitor] 检查关键词 '{kw['keyword']}' 异常: {e}")

    # 保存新结果
    MONITOR_DATA.setdefault('results', []).extend(all_new)
    # 只保留最近 500 条
    if len(MONITOR_DATA['results']) > 500:
        MONITOR_DATA['results'] = MONITOR_DATA['results'][-500:]
    _save_monitor(MONITOR_DATA)

    return jsonify({
        'success': True,
        'new_count': len(all_new),
        'data': all_new,
        'message': f'发现 {len(all_new)} 条新笔记',
    })


@app.route('/api/monitor/results', methods=['GET'])
def monitor_results():
    """获取监控结果"""
    keyword = request.args.get('keyword', '')
    limit = request.args.get('limit', 100, type=int)
    results = MONITOR_DATA.get('results', [])
    if keyword:
        results = [r for r in results if r.get('keyword') == keyword]
    return jsonify({'success': True, 'data': results[-limit:]})


@app.route('/api/monitor/results', methods=['DELETE'])
def monitor_clear_results():
    """清空监控结果"""
    MONITOR_DATA['results'] = []
    _save_monitor(MONITOR_DATA)
    return jsonify({'success': True, 'message': '已清空监控结果'})


@app.route('/api/monitor/analyze', methods=['POST'])
def monitor_analyze():
    """AI 情报分析：对监控到的笔记进行趋势分析"""
    data = request.json or {}
    keyword = data.get('keyword', '')

    if not CONFIG['llm_api_key']:
        return jsonify({'success': False, 'message': 'AI API Key 未配置'})

    # 获取该关键词的监控结果
    results = MONITOR_DATA.get('results', [])
    if keyword:
        results = [r for r in results if r.get('keyword') == keyword]

    if not results:
        return jsonify({'success': False, 'message': '没有监控到的数据可供分析'})

    # 构建分析 prompt
    notes_summary = []
    for r in results[-30:]:  # 最多分析30条
        notes_summary.append(
            f"- 标题: {r['title']}, 作者: {r['author']}, "
            f"点赞: {r.get('liked_count', 0)}, 评论: {r.get('comment_count', 0)}, "
            f"收藏: {r.get('collected_count', 0)}\n  摘要: {r.get('desc', '')[:100]}"
        )

    prompt = f"""你是一个小红书数据分析专家。请基于以下监控到的关于"{keyword}"的最新笔记数据，给出情报分析报告：

{chr(10).join(notes_summary)}

请从以下维度分析并用中文回答：
1. **热度趋势**：当前该话题的整体热度如何
2. **内容方向**：最受欢迎的内容类型和角度
3. **高赞特征**：高互动量笔记的共同特征（标题、内容风格、封面等）
4. **竞品洞察**：头部创作者是谁，他们在做什么
5. **机会建议**：如果要创作相关内容，建议的方向和策略

请给出结构化的分析报告，带具体数据支撑。"""

    try:
        # 直接复用 rewrite_note 的 LLM 调用通道
        backend = get_llm_backend()
        if not backend:
            return jsonify({'success': False, 'message': '创建 AI 后端失败，请检查 AI 配置'})

        system_prompt = "你是一个小红书数据分析专家，擅长从数据中提取趋势洞察。请用结构化中文回答。"
        analysis = backend.chat(system_prompt, prompt)

        return jsonify({
            'success': True,
            'data': {
                'analysis': analysis,
                'notes_count': len(results),
                'keyword': keyword or '(全部关键词)',
            }
        })
    except Exception as e:
        logger.exception(f"[monitor] AI 分析异常: {e}")
        return jsonify({'success': False, 'message': f'AI 分析失败: {str(e)}'})


# ═══════════════════════════════════════════════════════════════════════════════
# 功能 2: KOL 筛选 + 智能匹配
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/kol/search', methods=['POST'])
def kol_search():
    """搜索 KOL 用户"""
    data = request.json or {}
    keyword = data.get('keyword', '').strip()
    count = data.get('count', 20)

    if not keyword:
        return jsonify({'success': False, 'message': '请输入搜索关键词'})
    if not CONFIG['cookies']:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})

    try:
        time.sleep(random.uniform(0.5, 1.5))
        xhs = XHS_Apis()
        success, msg, users = xhs.search_some_user(keyword, count, CONFIG['cookies'])

        if not success:
            return jsonify({'success': False, 'message': f'搜索失败: {msg}'})

        kol_list = []
        for u in users:
            # XHS search_user API 返回扁平结构: {id, name, fans, red_id, note_count, image, profession, ...}
            # 兼容两种格式: 扁平结构和嵌套结构 (basic_info/interact_info)
            basic = u.get('basic_info', u)   # 扁平结构时 fallback 到 u 自身
            interact = u.get('interact_info', u)

            user_id = basic.get('user_id', '') or u.get('id', '')
            nickname = basic.get('nickname', '') or u.get('name', '')
            desc = basic.get('desc', '') or u.get('profession', '')
            red_id = basic.get('red_id', '') or u.get('red_id', '')
            image_url = u.get('image', '') or (basic.get('images', [None])[0] if basic.get('images') else '')

            # 粉丝数: 从 interact 或直接从 u 取
            fans_raw = interact.get('fans', 0) or u.get('fans', 0)
            fans = _parse_count(fans_raw)

            # 互动数据: 可能是嵌套结构或缺失
            interaction = interact.get('interaction', {})
            liked = _parse_count(interaction.get('liked', 0)) if interaction else 0
            collected = _parse_count(interaction.get('collected', 0)) if interaction else 0
            comment = _parse_count(interaction.get('comment', 0)) if interaction else 0
            interact_total = liked + collected + comment

            # 互动率 = 总互动 / 粉丝数（越高越好）
            engagement_rate = round(interact_total / max(fans, 1) * 100, 2)

            # KOL 综合评分 (0-100)
            score = _calc_kol_score(fans, interact_total, engagement_rate)

            kol_list.append({
                'user_id': user_id,
                'nickname': nickname,
                'desc': desc,
                'gender': basic.get('gender', ''),
                'red_id': red_id,
                'fans': fans,
                'fans_display': fans_raw,
                'liked': liked,
                'collected': collected,
                'comment': comment,
                'engagement_rate': engagement_rate,
                'score': score,
                'image': image_url,
                'note_count': u.get('note_count', 0),
                'update_time': u.get('update_time', ''),
                'is_official': u.get('red_official_verified', False),
                'xsec_token': u.get('xsec_token', ''),
            })

        # 按评分排序
        kol_list.sort(key=lambda x: x['score'], reverse=True)

        return jsonify({'success': True, 'data': kol_list, 'message': f'找到 {len(kol_list)} 个用户'})
    except Exception as e:
        logger.exception(f"[kol] 搜索异常: {e}")
        return jsonify({'success': False, 'message': f'搜索异常: {str(e)}'})


@app.route('/api/kol/profile', methods=['POST'])
def kol_profile():
    """获取 KOL 详细信息 + 最近笔记"""
    data = request.json or {}
    user_id = data.get('user_id', '').strip()
    user_url = data.get('url', '').strip()

    if not user_id and not user_url:
        return jsonify({'success': False, 'message': '请输入用户 ID 或主页链接'})
    if not CONFIG['cookies']:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})

    try:
        time.sleep(random.uniform(0.5, 1.5))
        xhs = XHS_Apis()

        # 获取用户信息
        if user_id:
            success, msg, user_info = xhs.get_user_info(user_id, CONFIG['cookies'])
        else:
            # 从 URL 提取 user_id，再获取用户信息
            urlParse = urllib.parse.urlparse(user_url)
            user_id = urlParse.path.split("/")[-1]
            success, msg, user_info = xhs.get_user_info(user_id, CONFIG['cookies'])

        if not success:
            return jsonify({'success': False, 'message': f'获取失败: {msg}'})

        # 获取用户笔记
        notes = []
        time.sleep(random.uniform(0.5, 1.5))
        try:
            nsuccess, nmsg, note_data = xhs.get_user_note_info(user_id, '', CONFIG['cookies'])
            if nsuccess and note_data:
                for n in note_data.get('notes', []):
                    nc = n.get('note_card', {})
                    interact = nc.get('interact_info', {})
                    notes.append({
                        'note_id': n.get('id', ''),
                        'title': nc.get('title', '') or nc.get('display_title', '') or n.get('display_title', '') or '(无标题)',
                        'desc': (nc.get('desc', '') or '')[:100],
                        'liked': interact.get('liked_count', '0'),
                        'collected': interact.get('collected_count', '0'),
                        'comment': interact.get('comment_count', '0'),
                        'type': nc.get('type', ''),
                    })
        except Exception as e:
            logger.warning(f"[kol] 获取笔记列表失败: {e}")

        return jsonify({
            'success': True,
            'data': {
                'user_info': user_info,
                'recent_notes': notes,
            }
        })
    except Exception as e:
        logger.exception(f"[kol] 获取详情异常: {e}")
        return jsonify({'success': False, 'message': f'获取异常: {str(e)}'})


@app.route('/api/kol/filter', methods=['POST'])
def kol_filter():
    """筛选 KOL 列表（前端过滤用，但也可后端过滤）"""
    data = request.json or {}
    min_fans = data.get('min_fans', 0)
    max_fans = data.get('max_fans', 999999999)
    min_engagement = data.get('min_engagement', 0)
    min_score = data.get('min_score', 0)
    kol_list = data.get('kol_list', [])

    filtered = []
    for kol in kol_list:
        fans = kol.get('fans', 0)
        eng = kol.get('engagement_rate', 0)
        score = kol.get('score', 0)
        if min_fans <= fans <= max_fans and eng >= min_engagement and score >= min_score:
            filtered.append(kol)

    return jsonify({'success': True, 'data': filtered, 'message': f'筛选出 {len(filtered)} 个 KOL'})


def _parse_count(val):
    """解析数量字符串（支持 '1.2万' 格式）"""
    if isinstance(val, (int, float)):
        return int(val)
    if not val:
        return 0
    val = str(val).strip()
    if '万' in val:
        try:
            return int(float(val.replace('万', '').strip()) * 10000)
        except:
            return 0
    try:
        return int(float(val))
    except:
        return 0


def _calc_kol_score(fans, total_interact, engagement_rate):
    """KOL 综合评分 (0-100)"""
    import math
    # 粉丝分 (0-40)
    fans_score = min(40, 40 * math.log10(max(fans, 1)) / math.log10(1000000))
    # 互动量分 (0-30)
    interact_score = min(30, 30 * math.log10(max(total_interact, 1)) / math.log10(1000000))
    # 互动率分 (0-30)：1-5% 最佳区间
    if engagement_rate >= 1 and engagement_rate <= 5:
        eng_score = 30
    elif engagement_rate < 1:
        eng_score = max(0, 30 * engagement_rate)
    else:
        eng_score = max(0, 30 - (engagement_rate - 5) * 2)  # 超过5%递减

    return round(fans_score + interact_score + eng_score, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 功能 3: 断点续传下载
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/download/batch', methods=['POST'])
def download_batch():
    """批量下载笔记的图片/视频，支持断点续传"""
    data = request.json or {}
    items = data.get('items', [])  # [{url, images: [...], note_id}]
    save_dir_name = data.get('folder', 'batch_download')

    if not items:
        return jsonify({'success': False, 'message': '没有下载任务'})

    import requests as req
    save_dir = os.path.join(os.path.dirname(__file__), 'static', save_dir_name)
    os.makedirs(save_dir, exist_ok=True)

    results = []
    total = sum(len(item.get('images', [])) for item in items)
    completed = 0

    for item in items:
        note_id = item.get('note_id', f"note_{int(time.time())}")
        images = item.get('images', [])
        item_dir = os.path.join(save_dir, note_id)
        os.makedirs(item_dir, exist_ok=True)

        item_result = {'note_id': note_id, 'files': [], 'failed': []}

        for idx, img_url in enumerate(images):
            file_key = f"{note_id}_{idx}"
            state = DOWNLOAD_STATE.get(file_key, {})

            # 断点续传：跳过已下载的
            if state.get('status') == 'done' and os.path.exists(state.get('path', '')):
                item_result['files'].append(state['path'])
                completed += 1
                continue

            filename = f"img_{idx + 1}.jpg"
            filepath = os.path.join(item_dir, filename)

            try:
                # 多 headers 下载（每组 headers 用新 dict，避免 Range 污染）
                header_sets = [
                    _XHS_IMG_HEADERS.copy(),
                    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://www.xiaohongshu.com/'},
                    {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'},
                ]

                success_dl = False
                for headers in header_sets:
                    try:
                        # 如果有部分下载记录，先尝试 Range 续传
                        resume_pos = state.get('downloaded', 0) if state.get('status') == 'partial' else 0
                        dl_headers = dict(headers)
                        if resume_pos > 0 and os.path.exists(filepath):
                            dl_headers['Range'] = f'bytes={resume_pos}-'
                            resp = req.request('GET', img_url, headers=dl_headers, timeout=30, stream=True)
                            if resp.status_code in (200, 206):
                                with open(filepath, 'ab') as f:
                                    for chunk in resp.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                resp.close()
                            else:
                                # 续传不支持，重新全量下载
                                resume_pos = 0
                                resp.close()

                        if resume_pos == 0:
                            resp = req.request('GET', img_url, headers=dl_headers, timeout=30, stream=True)
                            if resp.status_code == 200:
                                with open(filepath, 'wb') as f:
                                    for chunk in resp.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                resp.close()
                            else:
                                DOWNLOAD_STATE[file_key] = {
                                    'status': 'partial',
                                    'downloaded': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                                }
                                continue

                        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                        if file_size > 1000:
                            DOWNLOAD_STATE[file_key] = {
                                'status': 'done',
                                'path': f'/static/{save_dir_name}/{note_id}/{filename}',
                                'size': file_size,
                            }
                            _save_download_state(DOWNLOAD_STATE)
                            item_result['files'].append(f'/static/{save_dir_name}/{note_id}/{filename}')
                            success_dl = True
                            completed += 1
                            break
                        else:
                            # 文件太小，可能是防盗链拒绝
                            if os.path.exists(filepath):
                                os.remove(filepath)
                            DOWNLOAD_STATE[file_key] = {
                                'status': 'partial',
                                'downloaded': 0,
                            }
                    except Exception as e:
                        logger.warning(f"[download] 下载异常: {e}")
                        continue

                if not success_dl:
                    item_result['failed'].append(idx + 1)
                    DOWNLOAD_STATE[file_key] = {'status': 'failed'}
            except Exception as e:
                logger.warning(f"[download] 下载失败: {img_url[:60]} -> {e}")
                item_result['failed'].append(idx + 1)

        results.append(item_result)

    _save_download_state(DOWNLOAD_STATE)
    return jsonify({
        'success': True,
        'completed': completed,
        'total': total,
        'results': results,
        'message': f'下载完成 {completed}/{total}',
    })


@app.route('/api/download/resume', methods=['POST'])
def download_resume():
    """获取断点续传状态"""
    data = request.json or {}
    note_ids = data.get('note_ids', [])
    save_dir_name = data.get('folder', 'batch_download')

    status_list = []
    for note_id in note_ids:
        note_files = {}
        note_state = {'note_id': note_id, 'files': [], 'pending': []}
        for key, state in DOWNLOAD_STATE.items():
            if key.startswith(note_id):
                if state.get('status') == 'done':
                    note_state['files'].append(state)
                else:
                    note_state['pending'].append({**state, 'key': key})
        status_list.append(note_state)

    return jsonify({'success': True, 'data': status_list})


@app.route('/api/download/clear-state', methods=['POST'])
def download_clear_state():
    """清除下载状态"""
    global DOWNLOAD_STATE
    DOWNLOAD_STATE = {}
    _save_download_state(DOWNLOAD_STATE)
    return jsonify({'success': True, 'message': '下载状态已清除'})


# ═══════════════════════════════════════════════════════════════════════════════
# 功能 4: 批量用户主页采集
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/user/batch', methods=['POST'])
def user_batch_collect():
    """批量采集用户主页笔记"""
    data = request.json or {}
    user_urls = data.get('urls', [])  # 用户主页 URL 列表
    max_notes = data.get('max_notes', 50)  # 每个用户最多采集多少条

    if not user_urls:
        return jsonify({'success': False, 'message': '请输入至少一个用户主页链接'})
    if not CONFIG['cookies']:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})

    xhs = XHS_Apis()
    results = []

    for url in user_urls:
        url = url.strip()
        if not url:
            continue

        try:
            # 0. 解析短链接
            url = _resolve_short_url(url)

            # 批量模式下使用配置的延迟
            from utils.rate_limiter import rate_limiter
            batch_delay = random.uniform(rate_limiter.min_delay, rate_limiter.max_delay) if rate_limiter.min_delay > 0 else random.uniform(2.0, 5.0)
            time.sleep(batch_delay)

            # 1. 从 URL 中提取 user_id，获取用户信息
            urlParse = urllib.parse.urlparse(url)
            user_id = urlParse.path.split("/")[-1]
            user_info = {}
            try:
                uinfo_ok, uinfo_msg, uinfo_data = xhs.get_user_info(user_id, CONFIG['cookies'])
                if uinfo_ok and isinstance(uinfo_data, dict):
                    user_info = uinfo_data.get('data', {})
            except Exception as ue:
                logger.warning(f"[batch_user] 获取用户信息失败 {url}: {ue}")

            # 2. 获取用户全部笔记（返回值是 note_list）
            time.sleep(random.uniform(3.0, 8.0))
            success, msg, notes_raw = xhs.get_user_all_notes(url, CONFIG['cookies'])

            if not success:
                results.append({'url': url, 'success': False, 'message': msg, 'notes': []})
                continue

            # notes_raw 已经是 list，直接用
            if notes_raw is None:
                notes_raw = []

            notes = []
            for n in notes_raw[:max_notes]:
                nc = n.get('note_card', {})
                interact = nc.get('interact_info', {})
                note_id = n.get('id', '')
                xsec_token = n.get('xsec_token', '')

                # user_posted 列表 API 不返回互动数据，需要逐篇获取
                liked = interact.get('liked_count', '')
                collected = interact.get('collected_count', '')
                comment = interact.get('comment_count', '')

                # 如果列表 API 没给互动数据，尝试从详情获取
                # 注意：'not liked' 对 0 也是 True，所以用 is_empty 检查
                is_empty = (liked in ('', None) and collected in ('', None) and comment in ('', None))
                if is_empty and note_id:
                    try:
                        note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=app_share"
                        time.sleep(random.uniform(3.0, 8.0))
                        ni_ok, ni_msg, ni_data = xhs.get_note_info(note_url, CONFIG['cookies'])
                        if ni_ok and isinstance(ni_data, dict):
                            inner_data = ni_data.get('data', {})
                            items = []
                            if isinstance(inner_data, dict):
                                items = inner_data.get('items', [])
                                # 有时 data.note_card 在顶层
                                if not items and inner_data.get('note_card'):
                                    items = [inner_data]
                            if items:
                                detail = items[0].get('note_card', {})
                                detail_interact = detail.get('interact_info', {})
                                liked = detail_interact.get('liked_count', '0')
                                collected = detail_interact.get('collected_count', '0')
                                comment = detail_interact.get('comment_count', '0')
                                # 也补充 desc（列表 API 的 desc 可能被截断）
                                full_desc = detail.get('desc', '')
                                if full_desc:
                                    nc['desc'] = full_desc
                                logger.info(f"[batch_user] {note_id} 详情互动: 赞{liked} 藏{collected} 评{comment}")
                            else:
                                logger.warning(f"[batch_user] {note_id} get_note_info 返回空 items, data_keys={list(inner_data.keys()) if isinstance(inner_data, dict) else type(inner_data).__name__}")
                        else:
                            logger.warning(f"[batch_user] {note_id} get_note_info 失败: {ni_msg}")
                    except Exception as de:
                        logger.warning(f"[batch_user] 获取笔记详情异常 {note_id}: {de}")

                if liked is None or liked == '':
                    liked = '0'
                if collected is None or collected == '':
                    collected = '0'
                if comment is None or comment == '':
                    comment = '0'

                notes.append({
                    'note_id': note_id,
                    'title': nc.get('title', '') or nc.get('display_title', '') or n.get('display_title', '') or '(无标题)',
                    'desc': (nc.get('desc', '') or '')[:200],
                    'liked': liked,
                    'collected': collected,
                    'comment': comment,
                    'type': nc.get('type', ''),
                    'xsec_token': xsec_token,
                    # 图片
                    'images': [
                        img.get('info_list', [{}])[1 if len(img.get('info_list', [])) > 1 else 0].get('url', '')
                        if img.get('info_list')
                        else img.get('url_default', '')
                        for img in nc.get('image_list', [])
                        if img.get('info_list') or img.get('url_default')
                    ],
                })

            results.append({
                'url': url,
                'success': True,
                'user': {
                    'nickname': user_info.get('nickname', ''),
                    'user_id': user_info.get('user_id', ''),
                    'desc': user_info.get('desc', ''),
                    'fans': user_info.get('fans', 0),
                },
                'notes': notes,
                'total_notes': len(notes),
            })
        except Exception as e:
            logger.exception(f"[batch_user] 采集用户 {url} 异常: {e}")
            results.append({'url': url, 'success': False, 'message': str(e), 'notes': []})

    # 汇总统计
    total_notes = sum(len(r['notes']) for r in results)
    success_count = sum(1 for r in results if r['success'])
    return jsonify({
        'success': True,
        'data': results,
        'summary': {
            'total_users': len(user_urls),
            'success_users': success_count,
            'total_notes': total_notes,
        },
        'message': f'采集完成: {success_count}/{len(user_urls)} 个用户, 共 {total_notes} 条笔记',
    })


@app.route('/api/user/notes', methods=['POST'])
def user_notes():
    """采集单个用户的全部笔记（支持翻页）"""
    data = request.json or {}
    user_id = data.get('user_id', '').strip()
    cursor = data.get('cursor', '')

    if not user_id:
        return jsonify({'success': False, 'message': '请输入用户 ID'})
    if not CONFIG['cookies']:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})

    try:
        time.sleep(random.uniform(0.5, 1.5))
        xhs = XHS_Apis()
        success, msg, note_data = xhs.get_user_note_info(user_id, cursor, CONFIG['cookies'])

        if not success:
            return jsonify({'success': False, 'message': f'获取失败: {msg}'})

        notes = []
        for n in note_data.get('notes', []):
            nc = n.get('note_card', {})
            interact = nc.get('interact_info', {})
            notes.append({
                'note_id': n.get('id', ''),
                'title': nc.get('title', '') or nc.get('display_title', '') or n.get('display_title', '') or '(无标题)',
                'desc': (nc.get('desc', '') or '')[:200],
                'liked': interact.get('liked_count', '0'),
                'collected': interact.get('collected_count', '0'),
                'comment': interact.get('comment_count', '0'),
                'type': nc.get('type', ''),
                'xsec_token': n.get('xsec_token', ''),
            })

        return jsonify({
            'success': True,
            'data': notes,
            'has_more': note_data.get('has_more', False),
            'cursor': note_data.get('cursor', ''),
        })
    except Exception as e:
        logger.exception(f"[user_notes] 获取异常: {e}")
        return jsonify({'success': False, 'message': f'获取异常: {str(e)}'})


@app.route('/api/plugin/download', methods=['GET'])
def download_plugin():
    """下载 Chrome 插件 zip 包"""
    import zipfile
    import io

    plugin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'chrome_extension')
    if not os.path.exists(plugin_dir):
        return jsonify({'success': False, 'message': '插件目录不存在'}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(plugin_dir):
            for f in files:
                filepath = os.path.join(root, f)
                arcname = os.path.relpath(filepath, plugin_dir)
                zf.write(filepath, arcname)
    buf.seek(0)

    from flask import send_file
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name='xhs-cookie-collector.zip')


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"🥔 土豆小红书助手启动中...")
    logger.info(f"📡 访问地址: http://localhost:{port}")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=debug, allow_unsafe_werkzeug=True)
