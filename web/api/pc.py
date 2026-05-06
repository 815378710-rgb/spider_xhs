"""
PC端采集 API 蓝图
映射原项目 apis/xhs_pc_apis.py 的全部功能到 Web API
"""
import urllib
import requests as req_lib
from flask import Blueprint, request, jsonify

pc_bp = Blueprint('pc', __name__)


def _get_config():
    from app import CONFIG
    return CONFIG


def _get_json():
    """安全获取 JSON body，处理空 body / Content-Type 缺失 / None 的情况"""
    data = request.json
    if data is None or not isinstance(data, dict):
        return {}
    return data


def _require_cookies():
    """检查 Cookie 是否已配置，返回 (cookies_str, error_response)"""
    cfg = _get_config()
    if not cfg.get('cookies'):
        return None, jsonify({'success': False, 'msg': 'Cookie 未配置，请先在设置中登录'})
    return cfg['cookies'], None


# ── 主页频道 ──────────────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/homefeed/channels', methods=['GET'])
def homefeed_channels():
    """获取主页所有频道"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    success, msg, data = XHS_Apis().get_homefeed_all_channel(cookies)
    return jsonify({'success': success, 'msg': msg, 'data': data})


# ── 推荐笔记 ──────────────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/homefeed/recommend', methods=['POST'])
def homefeed_recommend():
    """获取推荐笔记"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    success, msg, result = XHS_Apis().get_homefeed_recommend_by_num(
        data.get('category', ''),
        data.get('num', 20),
        cookies,
        data.get('proxies')
    )
    return jsonify({'success': success, 'msg': msg, 'data': result})


# ── 笔记详情 ──────────────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/note/info', methods=['POST'])
def note_info():
    """获取笔记详情"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    note_url = data.get('url', '').strip()
    if not note_url:
        return jsonify({'success': False, 'msg': '请输入笔记链接'})
    success, msg, result = XHS_Apis().get_note_info(note_url, cookies)
    if not success:
        return jsonify({'success': False, 'msg': msg})
    try:
        note = result['data']['items'][0]
        note_card = note['note_card']
        images = []
        for img in note_card.get('image_list', []):
            if 'info_list' in img and len(img['info_list']) > 1:
                images.append(img['info_list'][1]['url'])
        return jsonify({
            'success': True,
            'data': {
                'note_id': note.get('id', ''),
                'title': note_card.get('title', ''),
                'desc': note_card.get('desc', ''),
                'images': images,
                'author': note_card.get('user', {}).get('nickname', ''),
                'author_id': note_card.get('user', {}).get('user_id', ''),
                'likes': note_card.get('interact_info', {}).get('liked_count', 0),
                'collects': note_card.get('interact_info', {}).get('collected_count', 0),
                'comments': note_card.get('interact_info', {}).get('comment_count', 0),
                'shares': note_card.get('interact_info', {}).get('share_count', 0),
                'type': note_card.get('type', ''),
                'tags': [t.get('name', '') for t in note_card.get('tag_list', [])],
                'time': note_card.get('time', 0),
                'ip_location': note_card.get('ip_location', ''),
                'raw': result,
            }
        })
    except (KeyError, IndexError) as e:
        return jsonify({'success': False, 'msg': f'解析笔记数据失败: {e}'})


# ── 无水印图片/视频 ─────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/note/no-watermark-img', methods=['POST'])
def no_watermark_img():
    """获取无水印图片"""
    from apis.xhs_pc_apis import XHS_Apis
    data = _get_json()
    img_url = data.get('url', '').strip()
    if not img_url:
        return jsonify({'success': False, 'msg': '请输入图片URL'})
    success, msg, url = XHS_Apis.get_note_no_water_img(img_url)
    return jsonify({'success': success, 'msg': msg, 'data': url})


@pc_bp.route('/api/pc/note/no-watermark-video', methods=['POST'])
def no_watermark_video():
    """获取无水印视频"""
    from apis.xhs_pc_apis import XHS_Apis
    data = _get_json()
    note_id = data.get('note_id', '').strip()
    if not note_id:
        return jsonify({'success': False, 'msg': '请输入笔记ID'})
    success, msg, url = XHS_Apis.get_note_no_water_video(note_id)
    return jsonify({'success': success, 'msg': msg, 'data': url})


# ── 用户信息 ──────────────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/user/info', methods=['POST'])
def user_info():
    """获取用户信息"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    user_id = data.get('user_id', '').strip()
    if not user_id:
        return jsonify({'success': False, 'msg': '请输入用户ID'})
    success, msg, result = XHS_Apis().get_user_info(user_id, cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result})


@pc_bp.route('/api/pc/user/self', methods=['GET'])
def user_self():
    """获取自己信息"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    success, msg, result = XHS_Apis().get_user_self_info(cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result})


# ── 用户笔记列表 ──────────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/user/notes', methods=['POST'])
def user_notes():
    """获取用户所有笔记"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    user_url = data.get('url', '').strip()
    if not user_url:
        return jsonify({'success': False, 'msg': '请输入用户主页链接'})
    success, msg, notes = XHS_Apis().get_user_all_notes(user_url, cookies)
    return jsonify({'success': success, 'msg': msg, 'data': notes, 'count': len(notes) if notes else 0})


@pc_bp.route('/api/pc/user/liked', methods=['POST'])
def user_liked():
    """获取用户喜欢的笔记"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    user_url = data.get('url', '').strip()
    if not user_url:
        return jsonify({'success': False, 'msg': '请输入用户主页链接'})
    success, msg, notes = XHS_Apis().get_user_all_like_note_info(user_url, cookies)
    return jsonify({'success': success, 'msg': msg, 'data': notes, 'count': len(notes) if notes else 0})


@pc_bp.route('/api/pc/user/collected', methods=['POST'])
def user_collected():
    """获取用户收藏的笔记"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    user_url = data.get('url', '').strip()
    if not user_url:
        return jsonify({'success': False, 'msg': '请输入用户主页链接'})
    success, msg, notes = XHS_Apis().get_user_all_collect_note_info(user_url, cookies)
    return jsonify({'success': success, 'msg': msg, 'data': notes, 'count': len(notes) if notes else 0})


# ── 搜索 ──────────────────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/search/notes', methods=['POST'])
def search_notes():
    """搜索笔记"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'success': False, 'msg': '请输入搜索关键词'})
    success, msg, notes = XHS_Apis().search_some_note(
        keyword,
        data.get('count', 10),
        cookies,
        sort_type_choice=data.get('sort_type', 0),
        note_type=data.get('note_type', 0),
        note_time=data.get('note_time', 0),
        note_range=data.get('note_range', 0),
        pos_distance=data.get('pos_distance', 0),
        geo=data.get('geo'),
    )
    return jsonify({'success': success, 'msg': msg, 'data': notes if notes else [], 'count': len(notes) if notes else 0})


@pc_bp.route('/api/pc/search/users', methods=['POST'])
def search_users():
    """搜索用户"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'success': False, 'msg': '请输入搜索关键词'})
    success, msg, users = XHS_Apis().search_some_user(keyword, data.get('count', 10), cookies)
    return jsonify({'success': success, 'msg': msg, 'data': users if users else [], 'count': len(users) if users else 0})


@pc_bp.route('/api/pc/search/keyword', methods=['POST'])
def search_keyword():
    """获取搜索关键词建议"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    word = data.get('word', '').strip()
    if not word:
        return jsonify({'success': False, 'msg': '请输入关键词'})
    success, msg, result = XHS_Apis().get_search_keyword(word, cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result})


# ── 评论 ──────────────────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/note/comments', methods=['POST'])
def note_comments():
    """获取笔记所有评论"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    data = _get_json()
    note_url = data.get('url', '').strip()
    if not note_url:
        return jsonify({'success': False, 'msg': '请输入笔记链接'})
    success, msg, comments = XHS_Apis().get_note_all_comment(note_url, cookies)
    return jsonify({'success': success, 'msg': msg, 'data': comments, 'count': len(comments) if comments else 0})


# ── 消息 ──────────────────────────────────────────────────────────────────────

@pc_bp.route('/api/pc/message/unread', methods=['GET'])
def message_unread():
    """获取未读消息"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    success, msg, result = XHS_Apis().get_unread_message(cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result})


@pc_bp.route('/api/pc/message/mentions', methods=['GET'])
def message_mentions():
    """获取全部@提醒"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    success, msg, result = XHS_Apis().get_all_metions(cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result, 'count': len(result) if result else 0})


@pc_bp.route('/api/pc/message/likes', methods=['GET'])
def message_likes():
    """获取赞和收藏通知"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    success, msg, result = XHS_Apis().get_all_likesAndcollects(cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result, 'count': len(result) if result else 0})


@pc_bp.route('/api/pc/message/connections', methods=['GET'])
def message_connections():
    """获取新增关注"""
    from apis.xhs_pc_apis import XHS_Apis
    cookies, err = _require_cookies()
    if err:
        return err
    success, msg, result = XHS_Apis().get_all_new_connections(cookies)
    return jsonify({'success': success, 'msg': msg, 'data': result, 'count': len(result) if result else 0})
