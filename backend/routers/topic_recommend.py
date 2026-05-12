"""
爆款选题推荐路由
"""
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from loguru import logger
from core.config import settings
from core.deps import get_current_user

router = APIRouter()


class TopicRecommendRequest(BaseModel):
    keyword: str
    count: int = 6


@router.post("/recommend")
async def recommend_topics(req: TopicRecommendRequest, user=Depends(get_current_user)):
    """AI 选题推荐"""
    try:
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        success, msg, data = xhs.search_note(
            req.keyword, settings.COOKIES,
            page=1, sort_type_choice=2,
        )
        if not success:
            return {"success": False, "message": f"搜索失败: {msg}"}

        items = data.get("data", {}).get("items", [])
        summaries = []
        for item in items[:10]:
            note_card = item.get("note_card", {})
            summaries.append({
                "title": note_card.get("display_title", ""),
                "type": note_card.get("type", ""),
                "likes": note_card.get("interact_info", {}).get("liked_count", "0"),
                "desc": note_card.get("desc", "")[:100],
            })

        from utils.rewrite import create_backend_from_env
        llm = create_backend_from_env()

        system_prompt = "你是一个小红书爆款选题分析师，擅长分析热门内容趋势并推荐选题。"
        user_prompt = f"""根据以下"{req.keyword}"领域的热门笔记数据，推荐 {req.count} 个有爆款潜力的选题方向。

热门笔记参考：
{json.dumps(summaries, ensure_ascii=False, indent=2)}

请返回 JSON 数组（不要用 markdown 代码块包裹），每个元素包含：
- "title": 选题标题（吸引人的小红书风格）
- "reason": 推荐理由（1-2句话）
- "heat": 热度预估（"高"/"中"/"低"）
- "note_type": 建议笔记类型（"图文"/"视频"）
- "tags": 建议标签数组（2-3个）

只返回 JSON 数组，不要其他文字。"""

        response = llm.chat(system_prompt, user_prompt)
        text = response.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        topics = json.loads(text)
        return {"success": True, "data": topics}
    except Exception as e:
        logger.exception(f"选题推荐异常: {e}")
        return {"success": False, "message": f"推荐失败: {str(e)[:100]}"}
