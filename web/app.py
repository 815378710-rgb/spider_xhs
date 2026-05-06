"""
土豆小红书助手 - Flask Web 应用
"""
# === 在所有 import 之前设置 Node.js 环境 ===
import os as _os
_project_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_node_modules = _os.path.join(_project_root, "node_modules")
if _os.path.isdir(_node_modules):
    # 只在 NODE_PATH 未设置时才设置，避免累积
    if not _os.environ.get("NODE_PATH"):
        _os.environ["NODE_PATH"] = _node_modules

# execjs 在 Windows Git Bash 下找不到 node，手动注册
import execjs
from execjs._external_runtime import ExternalRuntime as _ER
_node_cmd = r"D:\node.exe"
if _os.path.exists(_node_cmd):
    _node_rt = _ER("Node", [_node_cmd], execjs._runner_sources.Node)
    _node_rt._available = True
    execjs._runtimes._runtimes.insert(0, ("Node", _node_rt))
    print(f"[PATCH] Node runtime registered, available={execjs.get('Node').is_available()}")

import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit
from loguru import logger
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apis.xhs_pc_apis import XHS_Apis
from apis.xhs_pc_login_apis import XHSLoginApi
from utils.rewrite import create_backend, rewrite_note
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

# 全局配置
CONFIG = {
    'cookies': os.getenv('COOKIES', ''),
    'llm_provider': os.getenv('LLM_PROVIDER', 'deepseek'),
    'llm_api_key': os.getenv('LLM_API_KEY', ''),
    'llm_model': os.getenv('LLM_MODEL', 'deepseek-v3'),
    'llm_base_url': os.getenv('LLM_BASE_URL', ''),
}
logger.info(f"🤖 LLM: provider={CONFIG['llm_provider']}, model={CONFIG['llm_model']}, base_url={CONFIG['llm_base_url']}, key={'✅' if CONFIG['llm_api_key'] else '❌'}")

# 统计数据
STATS = {
    'total_processed': 0,
    'total_rewritten': 0,
    'today_processed': 0,
    'today_rewritten': 0,
    'last_date': datetime.now().strftime('%Y-%m-%d'),
}

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


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    return jsonify({
        'cookies_configured': bool(CONFIG['cookies']),
        'llm_provider': CONFIG['llm_provider'],
        'llm_model': CONFIG['llm_model'],
        'llm_configured': bool(CONFIG['llm_api_key']),
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
    
    return jsonify({'success': True, 'message': '配置已更新'})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计数据"""
    update_daily_stats()
    return jsonify(STATS)


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
        resp = req.get(target_url, headers=headers, timeout=10)
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
        logger.info(f"[DEBUG] execjs Node available: {execjs.get('Node').is_available()}")

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

        if success:
            # 扫码成功，获取用户信息并提取 cookie 字符串
            success2, user_info, cookies = login_api.get_user_info(cookies)
            cookies_str = login_api.cookies_to_str(cookies)

            # 自动保存到配置
            CONFIG['cookies'] = cookies_str

            # 加入 Cookie 池
            nickname = user_info.get('nickname', '未知') if success2 else '未知'
            _cookie_pool.add_cookie(cookies_str, username=nickname, is_valid=True)
            logger.info(f"[login] Cookie 已加入池: {nickname}")

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
        return jsonify({'success': False, 'message': f'异常: {str(e)}'})


@app.route('/api/login/phone/send', methods=['POST'])
def login_phone_send():
    """发送手机验证码"""
    from apis.xhs_pc_login_apis import XHSLoginApi
    data = request.json
    phone = data.get('phone', '').strip()
    if not phone:
        return jsonify({'success': False, 'message': '请输入手机号'})
    try:
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
    session = LOGIN_SESSIONS.get(session_id)
    if not session or session.get('type') != 'phone':
        return jsonify({'success': False, 'message': '会话不存在'})
    if time.time() - session['created_at'] > 300:
        LOGIN_SESSIONS.pop(session_id, None)
        return jsonify({'success': False, 'message': '验证码已过期'})
    try:
        login_api = session['login_api']
        success, msg, result = login_api.login_by_phone(session['phone'], code, session['cookies'])
        if not success:
            return jsonify({'success': False, 'message': msg})
        cookies = result['cookies']
        s2, user_info, cookies = login_api.get_user_info(cookies)
        cookies_str = login_api.cookies_to_str(cookies)
        CONFIG['cookies'] = cookies_str
        # 加入 Cookie 池
        nickname = user_info.get('nickname', '未知') if s2 else '未知'
        _cookie_pool.add_cookie(cookies_str, username=nickname, is_valid=True)
        LOGIN_SESSIONS.pop(session_id, None)
        return jsonify({'success': True, 'message': f'登录成功！用户: {nickname}', 'cookies': cookies_str})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ── Cookie 池 API ────────────────────────────────────────────────────────────

@app.route('/api/cookie/pool', methods=['GET'])
def cookie_pool_info():
    """获取 Cookie 池概览"""
    return jsonify({'success': True, 'data': _cookie_pool.get_pool_info()})


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
    best = _cookie_pool.get_best_cookie()
    if not best:
        return jsonify({'success': False, 'message': 'Cookie 池中没有有效 Cookie'})
    CONFIG['cookies'] = best
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
    
    if not CONFIG['cookies']:
        return jsonify({'success': False, 'message': 'Cookie 未配置'})
    
    try:
        xhs = XHS_Apis()
        success, msg, note_info = xhs.get_note_info(note_url, CONFIG['cookies'])
        
        if not success:
            return jsonify({'success': False, 'message': f'采集失败: {msg}'})
        
        note = note_info['data']['items'][0]
        note_card = note['note_card']
        
        # 提取图片
        images = []
        for img in note_card.get('image_list', []):
            if 'info_list' in img and len(img['info_list']) > 1:
                images.append(img['info_list'][1]['url'])
        
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


@app.route('/api/images/process', methods=['POST'])
def process_images_api():
    """图片防重处理"""
    data = request.json
    image_urls = data.get('urls', [])
    level = data.get('level', 'medium')
    
    if not image_urls:
        return jsonify({'success': False, 'message': '没有图片需要处理'})
    
    import requests as req
    
    processed = []
    errors = []
    
    for i, url in enumerate(image_urls):
        try:
            # 下载图片
            resp = req.get(url, timeout=15)
            resp.raise_for_status()
            
            # 防重处理
            from utils.image_processor import process_image
            processed_bytes = process_image(resp.content, level)
            
            # 保存到临时目录
            output_dir = os.path.join(os.path.dirname(__file__), 'static', 'processed')
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"processed_{int(time.time())}_{i}.jpg"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(processed_bytes)
            
            processed.append({
                'original': url,
                'processed': f'/static/processed/{filename}',
                'filename': filename,
            })
            
        except Exception as e:
            errors.append(f"图片 {i+1}: {str(e)}")
    
    return jsonify({
        'success': len(processed) > 0,
        'data': processed,
        'errors': errors,
        'message': f'处理完成 {len(processed)}/{len(image_urls)} 张',
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
        xhs = XHS_Apis()
        success, msg, notes = xhs.search_some_note(
            keyword, count, CONFIG['cookies'],
            sort_type_choice=sort_type,
            note_type=note_type
        )
        
        if not success:
            return jsonify({'success': False, 'message': f'搜索失败: {msg}'})
        
        # 过滤出笔记类型
        note_list = []
        for note in notes:
            if note.get('model_type') == 'note':
                note_list.append({
                    'id': note.get('id', ''),
                    'title': note.get('display_title', ''),
                    'author': note.get('user', {}).get('nickname', ''),
                    'likes': note.get('interact_info', {}).get('liked_count', 0),
                    'xsec_token': note.get('xsec_token', ''),
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
                url = data.get('url')
                style = data.get('style', '保持原风格')
                model_override = data.get('model', '')
                image_level = data.get('image_level', 'medium')
                
                # Step 1: 采集
                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'collect',
                    'message': '正在采集笔记...',
                    'progress': 10,
                })
                
                xhs = XHS_Apis()
                success, msg, note_info = xhs.get_note_info(url, CONFIG['cookies'])
                
                if not success:
                    socketio.emit('task_error', {'task_id': task_id, 'message': f'采集失败: {msg}'})
                    return
                
                note = note_info['data']['items'][0]['note_card']
                title = note.get('title', '')
                desc = note.get('desc', '')
                images = [img['info_list'][1]['url'] for img in note.get('image_list', []) if 'info_list' in img and len(img['info_list']) > 1]
                
                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'collect_done',
                    'message': f'采集成功: {title[:20]}...',
                    'progress': 30,
                    'data': {'title': title, 'desc': desc, 'images': images},
                })
                
                # Step 2: AI 改写
                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'rewrite',
                    'message': '正在 AI 改写...',
                    'progress': 40,
                })
                
                backend = get_llm_backend(model_override=model_override or None)
                result = rewrite_note(title, desc, backend, style=style)
                
                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'rewrite_done',
                    'message': '改写完成',
                    'progress': 60,
                    'data': result,
                })
                
                # Step 3: 图片处理
                socketio.emit('task_progress', {
                    'task_id': task_id,
                    'step': 'images',
                    'message': f'正在处理 {len(images)} 张图片...',
                    'progress': 70,
                })
                
                processed_images = []
                for i, img_url in enumerate(images):
                    try:
                        import requests as req
                        resp = req.get(img_url, timeout=15)
                        resp.raise_for_status()
                        
                        from utils.image_processor import process_image
                        processed_bytes = process_image(resp.content, image_level)
                        
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
                            'progress': 70 + int(20 * (i + 1) / len(images)),
                        })
                    except Exception as e:
                        logger.warning(f"图片处理失败: {e}")
                
                # 完成
                socketio.emit('task_complete', {
                    'task_id': task_id,
                    'data': {
                        'original': {'title': title, 'desc': desc},
                        'rewritten': result,
                        'images_original': images,
                        'images_processed': processed_images,
                    },
                })
                
                update_daily_stats()
                STATS['today_processed'] += 1
                STATS['today_rewritten'] += 1
                STATS['total_processed'] += 1
                STATS['total_rewritten'] += 1
                
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


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"🥔 土豆小红书助手启动中...")
    logger.info(f"📡 访问地址: http://localhost:{port}")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
