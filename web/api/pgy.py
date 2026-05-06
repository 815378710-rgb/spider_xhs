"""
蒲公英 KOL 数据 API 蓝图
映射原项目 apis/xhs_pugongying_apis.py 的全部功能
"""
from flask import Blueprint, request, jsonify
from loguru import logger

pgy_bp = Blueprint('pgy', __name__)


def _get_config():
    from app import CONFIG
    return CONFIG


@pgy_bp.route('/api/pgy/categories', methods=['GET'])
def categories():
    """获取所有类目"""
    from apis.xhs_pugongying_apis import PuGongYingAPI
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    pgy_cookie = cfg.get('pgy_cookies', cfg['cookies'])
    cookies = trans_cookies(pgy_cookie)
    try:
        result = PuGongYingAPI().get_all_categories(cookies)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})


@pgy_bp.route('/api/pgy/kol/list', methods=['POST'])
def kol_list():
    """获取 KOL 博主列表"""
    from apis.xhs_pugongying_apis import PuGongYingAPI
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    data = request.json
    pgy_cookie = cfg.get('pgy_cookies', cfg['cookies'])
    cookies = trans_cookies(pgy_cookie)
    try:
        users = PuGongYingAPI().get_some_user(data.get('num', 10), cookies, data.get('content_tag'))
        return jsonify({'success': True, 'data': users, 'count': len(users)})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})


@pgy_bp.route('/api/pgy/kol/detail', methods=['POST'])
def kol_detail():
    """获取 KOL 详细数据"""
    from apis.xhs_pugongying_apis import PuGongYingAPI
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    data = request.json
    pgy_cookie = cfg.get('pgy_cookies', cfg['cookies'])
    cookies = trans_cookies(pgy_cookie)
    user_id = data.get('user_id', '')
    try:
        pgy = PuGongYingAPI()
        detail = pgy.get_user_detail(user_id, cookies)
        fans = pgy.get_user_fans_detail(user_id, cookies)
        history = pgy.get_user_fans_history(user_id, cookies)
        notes = pgy.get_user_notes_detail(user_id, cookies)
        return jsonify({
            'success': True,
            'data': {
                'detail': detail,
                'fans': fans,
                'fans_history': history,
                'notes': notes,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})


@pgy_bp.route('/api/pgy/kol/invite', methods=['POST'])
def kol_invite():
    """发起合作邀请"""
    from apis.xhs_pugongying_apis import PuGongYingAPI
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    data = request.json
    pgy_cookie = cfg.get('pgy_cookies', cfg['cookies'])
    cookies = trans_cookies(pgy_cookie)
    try:
        result = PuGongYingAPI().send_invite(
            data.get('user_id', ''),
            cookies,
            data.get('product_name', ''),
            data.get('time', []),
            data.get('content', ''),
            data.get('contact', ''),
        )
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
