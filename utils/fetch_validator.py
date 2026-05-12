"""
数据抓取验证模块 — 多层校验抓取结果
- HTTP状态码校验
- JSON解析校验
- API返回码校验
- 数据非空校验
- 核心字段校验
"""
from loguru import logger


def validate_fetch_result(response, expected_type="auto") -> dict:
    """
    多层校验抓取结果

    Args:
        response: httpx.Response 或 requests.Response
        expected_type: "auto" | "note" | "user" | "search"

    Returns:
        {
            "success": bool,      # 至少通过n-1项
            "status_code": int,
            "completeness": float, # 0-1
            "checks": dict,       # 各项检查结果
            "error": str,
            "data": dict | None,  # 解析后的JSON数据
            "cookie_expired": bool,
        }
    """
    checks = {}
    data = None
    error = ""
    cookie_expired = False

    try:
        # 1. HTTP状态码
        status_code = getattr(response, 'status_code', 0)
        checks["status_ok"] = status_code == 200

        # 2. JSON解析
        try:
            if hasattr(response, 'json'):
                data = response.json()
            elif hasattr(response, 'text'):
                import json
                data = json.loads(response.text)
            else:
                error = "无法解析响应"
                return {
                    "success": False, "status_code": status_code,
                    "completeness": 0, "checks": checks, "error": error,
                    "data": None, "cookie_expired": False,
                }
        except Exception:
            error = "响应不是有效JSON"
            return {
                "success": False, "status_code": status_code,
                "completeness": 0, "checks": checks, "error": error,
                "data": None, "cookie_expired": False,
            }

        # 3. API返回码
        api_code = data.get("code", -1)
        checks["api_code_ok"] = api_code == 0

        if api_code in (-9001, -10001, -9999):
            cookie_expired = True
            error = "Cookie已过期"

        # 4. 数据非空
        has_data = bool(data.get("data"))
        checks["has_data"] = has_data

        # 5. 核心字段检查（根据类型）
        if expected_type == "note" and has_data:
            note_data = data.get("data", {})
            # 可能嵌套在 items[0].note_card
            if "items" in note_data and note_data["items"]:
                note_data = note_data["items"][0].get("note_card", {})
            checks["has_title"] = bool(note_data.get("title") or note_data.get("desc"))
            checks["content_length"] = len(str(note_data.get("desc", ""))) > 5
        elif expected_type == "user" and has_data:
            user_data = data.get("data", {})
            checks["has_title"] = bool(user_data.get("basic_info", {}).get("nickname"))
            checks["content_length"] = True
        else:
            checks["has_title"] = True
            checks["content_length"] = True

        passed = sum(checks.values())
        total = len(checks)

        return {
            "success": passed >= max(4, total - 1),
            "status_code": status_code,
            "completeness": round(passed / total, 2),
            "checks": checks,
            "error": error,
            "data": data,
            "cookie_expired": cookie_expired,
        }
    except Exception as e:
        logger.error(f"[fetch_validator] 验证异常: {e}")
        return {
            "success": False,
            "status_code": getattr(response, 'status_code', 0),
            "completeness": 0,
            "checks": checks,
            "error": f"验证异常: {e}",
            "data": None,
            "cookie_expired": False,
        }
