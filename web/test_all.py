"""
土豆小红书助手 - 全功能测试脚本
模拟用户走遍所有流程，找 bug
"""
import json
import sys
import time

BASE = "http://localhost:5000"
PASS = 0
FAIL = 0
BUGS = []

def test(name, method, path, data=None, expect_success=None, expect_status=None):
    """发送请求并检查结果"""
    import urllib.request
    global PASS, FAIL
    
    url = BASE + path
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body_text = resp.read().decode()
            try:
                result = json.loads(body_text)
            except:
                result = {"_raw": body_text[:200]}
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            result = json.loads(e.read().decode())
        except:
            result = {"_error": str(e)}
    except Exception as e:
        status = 0
        result = {"_error": str(e)}
    
    # 检查
    ok = True
    issue = ""
    
    if expect_status and status != expect_status:
        ok = False
        issue = f"期望HTTP {expect_status}，实际 {status}"
    
    if expect_success is not None:
        actual = result.get('success')
        if actual != expect_success:
            ok = False
            issue = f"期望 success={expect_success}，实际 {actual}"
    
    if ok:
        PASS += 1
        icon = "✅"
    else:
        FAIL += 1
        BUGS.append(f"{name}: {issue}")
        icon = "❌"
    
    result_short = str(result)[:120]
    print(f"  {icon} [{status}] {name}")
    if not ok:
        print(f"     → {issue}")
        print(f"     → 返回: {result_short}")
    
    return status, result


def main():
    global PASS, FAIL
    print("=" * 60)
    print("🥔 土豆小红书助手 - 全功能测试")
    print("=" * 60)
    
    # ── 1. 基础页面 ──
    print("\n[1/10] 基础页面")
    test("首页加载", "GET", "/", expect_status=200)
    
    # ── 2. 配置接口 ──
    print("\n[2/10] 配置管理")
    s, r = test("获取配置", "GET", "/api/config", expect_success=None)
    assert s == 200, "配置接口返回非200"
    
    test("保存配置", "POST", "/api/config", {
        "llm_provider": "deepseek",
        "llm_api_key": "sk-test",
        "llm_model": "deepseek-v3"
    }, expect_success=True)
    
    s, r = test("验证配置已更新", "GET", "/api/config")
    assert r.get('llm_provider') == 'deepseek', "配置未保存"
    assert r.get('llm_configured') == True, "API Key未生效"
    
    # ── 3. 统计接口 ──
    print("\n[3/10] 统计接口")
    s, r = test("获取统计", "GET", "/api/stats", expect_status=200)
    assert 'total_processed' in r, "统计字段缺失"
    
    # ── 4. Cookie 测试 ──
    print("\n[4/10] Cookie 测试")
    test("空Cookie测试", "POST", "/api/test-cookie", {"cookies": ""}, expect_success=False)
    test("无效Cookie测试", "POST", "/api/test-cookie", {"cookies": "invalid_cookie=abc"}, expect_success=False)
    
    # ── 5. 扫码登录 ──
    print("\n[5/10] 扫码登录")
    s, r = test("获取二维码", "POST", "/api/login/qrcode")
    qr_session = r.get('session_id', '')
    qr_url = r.get('qr_url', '')
    if qr_session:
        print(f"     → session_id: {qr_session[:20]}...")
        print(f"     → qr_url: {qr_url[:60]}...")
        test("轮询扫码状态(等待中)", "POST", "/api/login/check", {"session_id": qr_session}, expect_success=False)
        test("轮询扫码状态(无效session)", "POST", "/api/login/check", {"session_id": "fake_session"}, expect_success=False)
    else:
        print("     ⚠️ 二维码获取失败（可能网络问题）")
    
    # ── 6. 手机登录 ──
    print("\n[6/10] 手机登录")
    test("空手机号", "POST", "/api/login/phone/send", {"phone": ""}, expect_success=False)
    # 注意：下面这个会真的调API，但没真实手机号不会成功
    test("发送验证码(无效)", "POST", "/api/login/phone/send", {"phone": "13800000000"})
    test("验证(无效session)", "POST", "/api/login/phone/verify", {"session_id": "fake", "code": "123"}, expect_success=False)
    
    # ── 7. PC 采集 API（无Cookie会失败，但测试路由是否存在）──
    print("\n[7/10] PC 采集 API (无Cookie，验证路由)")
    test("笔记详情(无url)", "POST", "/api/pc/note/info", {}, expect_success=False)
    test("笔记详情(有url无cookie)", "POST", "/api/pc/note/info", 
         {"url": "https://www.xiaohongshu.com/explore/test"})
    test("用户信息(无参数)", "POST", "/api/pc/user/info", {}, expect_success=False)
    test("自己信息", "GET", "/api/pc/user/self")
    test("搜索笔记(无关键词)", "POST", "/api/pc/search/notes", {}, expect_success=False)
    test("搜索笔记(有关键词)", "POST", "/api/pc/search/notes", {"keyword": "测试", "count": 5})
    test("搜索用户", "POST", "/api/pc/search/users", {"keyword": "测试", "count": 5})
    test("关键词建议", "POST", "/api/pc/search/keyword", {"word": "防"})
    test("用户笔记(无url)", "POST", "/api/pc/user/notes", {}, expect_success=False)
    test("用户喜欢(无url)", "POST", "/api/pc/user/liked", {}, expect_success=False)
    test("用户收藏(无url)", "POST", "/api/pc/user/collected", {}, expect_success=False)
    test("笔记评论(无url)", "POST", "/api/pc/note/comments", {}, expect_success=False)
    test("无水印图片", "POST", "/api/pc/note/no-watermark-img", {"url": "https://test.com/img.jpg"})
    test("无水印视频", "POST", "/api/pc/note/no-watermark-video", {"note_id": "test"})
    test("主页频道", "GET", "/api/pc/homefeed/channels")
    test("推荐笔记", "POST", "/api/pc/homefeed/recommend", {"category": "", "num": 5})
    test("未读消息", "GET", "/api/pc/message/unread")
    test("@提醒", "GET", "/api/pc/message/mentions")
    test("赞和收藏", "GET", "/api/pc/message/likes")
    test("新增关注", "GET", "/api/pc/message/connections")
    
    # ── 8. 创作者 API ──
    print("\n[8/10] 创作者 API (路由验证)")
    test("搜索话题", "POST", "/api/creator/topic/search", {"keyword": "穿搭"})
    test("搜索地点", "POST", "/api/creator/location/search", {"keyword": "北京"})
    test("创作者登录二维码", "POST", "/api/creator/login/qrcode")
    test("已发布列表", "GET", "/api/creator/publish/list")
    test("转码状态", "POST", "/api/creator/transcode/status", {"video_id": "test123"})
    
    # ── 9. 蒲公英/千帆 API ──
    print("\n[9/10] 蒲公英/千帆 API (路由验证)")
    test("蒲公英类目", "GET", "/api/pgy/categories")
    test("KOL列表", "POST", "/api/pgy/kol/list", {"num": 5})
    test("KOL详情", "POST", "/api/pgy/kol/detail", {"user_id": "test"})
    test("千帆品类", "GET", "/api/qf/categories")
    test("分销商列表", "POST", "/api/qf/distributor/list", {"num": 5})
    test("分销商详情", "POST", "/api/qf/distributor/detail", {"user_id": "test"})
    
    # ── 10. AI 改写 & 图片处理 ──
    print("\n[10/10] AI 改写 & 图片处理")
    test("改写(无内容)", "POST", "/api/note/rewrite", {"title": "", "desc": ""}, expect_success=False)
    test("改写(无API Key)", "POST", "/api/note/rewrite", {"title": "测试", "desc": "内容"})
    test("采集(无url)", "POST", "/api/note/collect", {}, expect_success=False)
    test("图片处理(无图片)", "POST", "/api/images/process", {"urls": []}, expect_success=False)
    test("批量搜索(无关键词)", "POST", "/api/batch/search", {}, expect_success=False)
    test("批量搜索(有关键词)", "POST", "/api/batch/search", {"keyword": "防晒", "count": 5})
    
    # ── 结果汇总 ──
    print("\n" + "=" * 60)
    print(f"📊 测试结果: ✅ {PASS} 通过 / ❌ {FAIL} 失败")
    if BUGS:
        print(f"\n🐛 发现的 Bug:")
        for i, bug in enumerate(BUGS, 1):
            print(f"   {i}. {bug}")
    else:
        print("🎉 全部通过，没有发现 Bug！")
    print("=" * 60)
    
    return FAIL


if __name__ == "__main__":
    sys.exit(main())
