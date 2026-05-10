"""
图片处理路由
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


@router.post("/process")
async def process_images(req: ImageProcessRequest, user=Depends(get_current_user)):
    """Process images with anti-duplicate processor."""
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
                # Decode base64
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
