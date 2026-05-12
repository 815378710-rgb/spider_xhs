"""
图片处理路由 — 传统防重 + AI 风格重绘
"""
import base64
import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.deps import get_current_user
from loguru import logger

router = APIRouter()


class ImageProcessRequest(BaseModel):
    images: list[str]  # base64 encoded images or URLs
    preset: str = "medium"  # light, medium, heavy


class AIRedrawRequest(BaseModel):
    images: list[str]  # base64 encoded images
    style: str = "清新风"  # 风格选择


@router.post("/process")
async def process_images(req: ImageProcessRequest, user=Depends(get_current_user)):
    """传统防重图片处理"""
    try:
        from utils.image_processor import ImageProcessor
        import cv2
        import numpy as np

        presets = {
            "light": {"brightness_range": (-5, 5), "contrast_range": (0.97, 1.03)},
            "medium": {"brightness_range": (-10, 10), "contrast_range": (0.95, 1.05)},
            "heavy": {"brightness_range": (-20, 20), "contrast_range": (0.90, 1.10)},
        }
        processor = ImageProcessor(**presets.get(req.preset, presets["medium"]))

        results = []
        for img_data in req.images[:10]:
            try:
                if img_data.startswith("data:"):
                    img_data = img_data.split(",", 1)[1]
                img_bytes = base64.b64decode(img_data)
                nparr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    results.append({"success": False, "message": "图片解码失败"})
                    continue

                processed = processor.process(img)
                _, buffer = cv2.imencode(".jpg", processed, [cv2.IMWRITE_JPEG_QUALITY, 95])
                b64_result = base64.b64encode(buffer).decode()
                results.append({"success": True, "image": f"data:image/jpeg;base64,{b64_result}"})
            except Exception as e:
                results.append({"success": False, "message": str(e)})

        return {"success": True, "data": results}
    except Exception as e:
        logger.exception(f"图片处理异常: {e}")
        return {"success": False, "message": f"处理失败: {str(e)[:100]}"}


@router.post("/ai-redraw")
async def ai_redraw(req: AIRedrawRequest, user=Depends(get_current_user)):
    """AI 风格重绘"""
    try:
        from utils.ai_image_style import apply_style, STYLE_PRESETS

        if req.style not in STYLE_PRESETS:
            available = list(STYLE_PRESETS.keys())
            return {"success": False, "message": f"未知风格: {req.style}，可选: {available}"}

        results = []
        for img_data in req.images[:5]:
            try:
                if img_data.startswith("data:"):
                    img_data = img_data.split(",", 1)[1]
                img_bytes = base64.b64decode(img_data)
                result_bytes = apply_style(img_bytes, req.style)
                b64_result = base64.b64encode(result_bytes).decode()
                results.append({"success": True, "image": f"data:image/jpeg;base64,{b64_result}"})
            except Exception as e:
                results.append({"success": False, "message": str(e)})

        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": True,
            "data": results,
            "styles": list(STYLE_PRESETS.keys()),
            "message": f"风格化处理完成: {success_count}/{len(req.images[:5])}",
        }
    except Exception as e:
        logger.exception(f"AI重绘异常: {e}")
        return {"success": False, "message": f"处理失败: {str(e)[:100]}"}


@router.get("/styles")
async def get_styles(user=Depends(get_current_user)):
    """获取可用的 AI 风格列表"""
    from utils.ai_image_style import get_available_styles
    return {"success": True, "data": get_available_styles()}


@router.get("/proxy")
async def image_proxy(url: str):
    """Proxy XHS CDN images to bypass CORS."""
    import requests as req
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.xiaohongshu.com/",
    }
    try:
        resp = req.request("GET", url, headers=headers, timeout=20)
        if resp.status_code == 200:
            from fastapi.responses import Response
            return Response(content=resp.content, media_type="image/jpeg")
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}
