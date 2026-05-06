"""
千帆分销商 API 蓝图
映射原项目 apis/xhs_qianfan_apis.py 的全部功能
"""
from flask import Blueprint, request, jsonify
from loguru import logger

qf_bp = Blueprint('qianfan', __name__)


def _get_config():
    from app import CONFIG
    return CONFIG


@qf_bp.route('/api/qf/categories', methods=['GET'])
def categories():
    """获取分销品类"""
    from apis.xhs_qianfan_apis import QianFanAPI
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    pgy_cookie = cfg.get('pgy_cookies', cfg['cookies'])
    cookies = trans_cookies(pgy_cookie)
    try:
        result = QianFanAPI().get_all_categories(cookies)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})


@qf_bp.route('/api/qf/distributor/list', methods=['POST'])
def distributor_list():
    """获取分销商列表"""
    from apis.xhs_qianfan_apis import QianFanAPI
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    data = request.json
    pgy_cookie = cfg.get('pgy_cookies', cfg['cookies'])
    cookies = trans_cookies(pgy_cookie)
    try:
        users = QianFanAPI().get_some_user(
            data.get('choice', '-1'),
            data.get('categories', []),
            data.get('num', 10),
            cookies
        )
        return jsonify({'success': True, 'data': users, 'count': len(users)})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})


@qf_bp.route('/api/qf/distributor/detail', methods=['POST'])
def distributor_detail():
    """获取分销商详情"""
    from apis.xhs_qianfan_apis import QianFanAPI
    from xhs_utils.cookie_util import trans_cookies
    cfg = _get_config()
    data = request.json
    pgy_cookie = cfg.get('pgy_cookies', cfg['cookies'])
    cookies = trans_cookies(pgy_cookie)
    user_id = data.get('user_id', '')
    try:
        qf = QianFanAPI()
        detail = qf.get_user_detail(user_id, cookies)
        cooperation = qf.get_user_cooperation(user_id, cookies)
        fans = qf.get_user_fans(user_id, cookies)
        return jsonify({
            'success': True,
            'data': {
                'detail': detail,
                'cooperation': cooperation,
                'fans': fans,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
