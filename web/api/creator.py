"""
创作者平台 API 蓝图
映射原项目 apis/xhs_creator_apis.py + apis/xhs_creator_login_apis.py 的全部功能
"""
from flask import Blueprint, request, jsonify
from loguru import logger

creator_bp = Blueprint('creator', __name__)


def _get_config():
    from app import CONFIG
    return CONFIG


@creator_bp.route('/api/creator/topic/search', methods=['POST'])
def topic_search():
    """搜索话题"""
    from apis.xhs_creator_apis import XHS_Creator_Apis
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    data = request.json
    cookies = trans_cookies(cfg['cookies'])
    success, msg, result = XHS_Creator_Apis().get_topic(data.get('keyword', ''), cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result})


@creator_bp.route('/api/creator/location/search', methods=['POST'])
def location_search():
    """搜索地点"""
    from apis.xhs_creator_apis import XHS_Creator_Apis
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    data = request.json
    cookies = trans_cookies(cfg['cookies'])
    success, msg, result = XHS_Creator_Apis().get_location_info(data.get('keyword', ''), cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result})


@creator_bp.route('/api/creator/publish', methods=['POST'])
def publish_note():
    """发布笔记（图集/视频）"""
    from apis.xhs_creator_apis import XHS_Creator_Apis
    cfg = _get_config()
    # 注意：这里需要 creator 平台的 cookie，不是 PC 端的
    creator_cookies_str = cfg.get('creator_cookies', cfg['cookies'])
    if not creator_cookies_str:
        return jsonify({'success': False, 'msg': '创作者平台 Cookie 未配置'})

    try:
        # 这里接收的是 JSON 元数据，图片/视频文件需要单独上传接口
        note_info = request.json
        success, msg, result = XHS_Creator_Apis().post_note(note_info, creator_cookies_str)
        return jsonify({'success': success, 'msg': msg, 'data': result})
    except Exception as e:
        logger.exception(f"发布笔记异常: {e}")
        return jsonify({'success': False, 'msg': str(e)})


@creator_bp.route('/api/creator/publish/list', methods=['GET'])
def published_list():
    """获取已发布笔记列表"""
    from apis.xhs_creator_apis import XHS_Creator_Apis
    cfg = _get_config()
    creator_cookies_str = cfg.get('creator_cookies', cfg['cookies'])
    if not creator_cookies_str:
        return jsonify({'success': False, 'msg': '创作者平台 Cookie 未配置'})
    success, msg, result = XHS_Creator_Apis().get_all_publish_note_info(creator_cookies_str)
    return jsonify({'success': success, 'msg': msg, 'data': result})


@creator_bp.route('/api/creator/transcode/status', methods=['POST'])
def transcode_status():
    """查询视频转码状态"""
    from apis.xhs_creator_apis import XHS_Creator_Apis
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    data = request.json
    cookies = trans_cookies(cfg.get('creator_cookies', cfg['cookies']))
    success, msg, result = XHS_Creator_Apis().query_transcode(data.get('video_id', ''), cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result})


@creator_bp.route('/api/creator/login/qrcode', methods=['POST'])
def creator_login_qrcode():
    """创作者平台扫码登录"""
    from apis.xhs_creator_login_apis import XHSCreatorLoginApi
    import time

    try:
        login_api = XHSCreatorLoginApi()
        cookies = login_api.generate_init_cookies()
        success, msg, qr_data = login_api.generate_qrcode(cookies)
        if not success:
            return jsonify({'success': False, 'msg': f'获取二维码失败: {msg}'})

        from app import LOGIN_SESSIONS
        session_id = f"creator_login_{int(time.time() * 1000)}"
        LOGIN_SESSIONS[session_id] = {
            'cookies': qr_data['cookies'],
            'qr_id': qr_data['qr_id'],
            'qr_url': qr_data['qr_url'],
            'login_api': login_api,
            'type': 'creator',
            'created_at': time.time(),
        }
        return jsonify({'success': True, 'session_id': session_id, 'qr_url': qr_data['qr_url']})
    except Exception as e:
        logger.exception(f"创作者扫码登录异常: {e}")
        return jsonify({'success': False, 'msg': str(e)})


@creator_bp.route('/api/creator/login/check', methods=['POST'])
def creator_login_check():
    """创作者平台扫码状态检查"""
    from app import LOGIN_SESSIONS
    import time

    data = request.json
    session_id = data.get('session_id', '')
    session = LOGIN_SESSIONS.get(session_id)
    if not session or session.get('type') != 'creator':
        return jsonify({'success': False, 'msg': '会话不存在或已过期'})

    if time.time() - session['created_at'] > 300:
        LOGIN_SESSIONS.pop(session_id, None)
        return jsonify({'success': False, 'msg': '二维码已过期，请重新获取'})

    try:
        login_api = session['login_api']
        cookies = session['cookies']
        success, msg, cookies = login_api.check_qrcode_status(session['qr_id'], cookies)
        session['cookies'] = cookies

        if success:
            success2, user_info, cookies = login_api.get_user_info(cookies)
            cookies_str = login_api.cookies_to_str(cookies)
            from app import CONFIG
            CONFIG['creator_cookies'] = cookies_str
            LOGIN_SESSIONS.pop(session_id, None)
            nickname = user_info.get('userName', '未知') if success2 else '未知'
            return jsonify({'success': True, 'msg': f'登录成功！用户: {nickname}', 'cookies': cookies_str})
        else:
            return jsonify({'success': False, 'msg': msg})
    except Exception as e:
        logger.exception(f"检查扫码状态异常: {e}")
        return jsonify({'success': False, 'msg': str(e)})
