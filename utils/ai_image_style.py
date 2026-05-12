"""
AI 图片风格化模块
使用 OpenCV 高级滤镜组合实现 6 种风格迁移效果
无需外部 AI 模型，纯本地图像处理
"""
import random
import math
import cv2
import numpy as np
from loguru import logger

# ── 风格预设定义 ─────────────────────────────────────────────────────────────

STYLE_PRESETS = {
    "漫画风": {"description": "边缘增强 + 颜色量化 + 高饱和度，模拟漫画效果"},
    "油画风": {"description": "双边滤波 + 形态学处理，模拟油画笔触"},
    "水彩风": {"description": "高斯模糊混合 + 饱和度提升，模拟水彩画效果"},
    "复古风": {"description": "棕褐色调 + 暗角 + 噪点，模拟老照片风格"},
    "清新风": {"description": "亮度提升 + 暖色调 + 饱和度微调，清新明亮风格"},
    "赛博朋克": {"description": "色相偏移 + 对比度增强 + 边缘高亮，霓虹灯效果"},
}


# ── 风格实现 ─────────────────────────────────────────────────────────────────

def _style_manga(img: np.ndarray) -> np.ndarray:
    """漫画风：边缘检测 + 颜色量化 + 饱和度增强"""
    # 1. 边缘检测
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 5
    )
    edges_3ch = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    # 2. 颜色量化（减少颜色数量）
    data = img.reshape((-1, 3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    k = 12  # 聚类数
    _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS)
    centers = np.uint8(centers)
    quantized = centers[labels.flatten()].reshape(img.shape)

    # 3. 饱和度增强
    hsv = cv2.cvtColor(quantized, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.6, 0, 255)
    enhanced = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 4. 混合边缘
    result = cv2.bitwise_and(enhanced, edges_3ch)
    return result


def _style_oil_painting(img: np.ndarray) -> np.ndarray:
    """油画风：双边滤波 + 形态学操作"""
    # 1. 多次双边滤波（模拟油画笔触）
    result = img.copy()
    for _ in range(3):
        result = cv2.bilateralFilter(result, d=9, sigmaColor=75, sigmaSpace=7)

    # 2. 形态学闭操作（连接色块）
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)

    # 3. 轻微锐化（保持细节）
    kernel_sharpen = np.array([[-0.5, -0.5, -0.5],
                                [-0.5, 5.0, -0.5],
                                [-0.5, -0.5, -0.5]])
    result = cv2.filter2D(result, -1, kernel_sharpen)
    result = np.clip(result, 0, 255).astype(np.uint8)

    return result


def _style_watercolor(img: np.ndarray) -> np.ndarray:
    """水彩风：高斯模糊混合 + 饱和度提升"""
    # 1. 边缘保留滤波
    result = cv2.edgePreservingFilter(img, flags=2, sigma_s=60, sigma_r=0.5)

    # 2. 轻微高斯模糊（柔和感）
    blurred = cv2.GaussianBlur(result, (5, 5), 0)

    # 3. 与原图混合（保留部分细节）
    result = cv2.addWeighted(blurred, 0.7, result, 0.3, 0)

    # 4. 饱和度提升
    hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.4, 0, 255)
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 5. 轻微提亮
    result = np.clip(result.astype(np.float32) * 1.05, 0, 255).astype(np.uint8)

    return result


def _style_vintage(img: np.ndarray) -> np.ndarray:
    """复古风：棕褐色调 + 暗角 + 噪点"""
    # 1. 转灰度再着色（棕褐色调）
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sepia = np.zeros((*gray.shape, 3), dtype=np.uint8)
    sepia[:, :, 0] = np.clip(gray * 0.8, 0, 255).astype(np.uint8)   # B
    sepia[:, :, 1] = np.clip(gray * 0.65, 0, 255).astype(np.uint8)  # G
    sepia[:, :, 2] = np.clip(gray * 0.5, 0, 255).astype(np.uint8)   # R

    # 2. 暗角效果
    h, w = sepia.shape[:2]
    Y, X = np.ogrid[:h, :w]
    center_y, center_x = h / 2, w / 2
    dist = np.sqrt((X - center_x) ** 2 + (Y - center_y) ** 2)
    max_dist = np.sqrt(center_x ** 2 + center_y ** 2)
    vignette = 1 - 0.6 * (dist / max_dist) ** 2
    vignette = np.clip(vignette, 0, 1)
    vignette_3ch = np.stack([vignette] * 3, axis=-1)
    sepia = np.clip(sepia.astype(np.float32) * vignette_3ch, 0, 255).astype(np.uint8)

    # 3. 轻微噪点
    noise = np.random.normal(0, 4, sepia.shape).astype(np.float32)
    sepia = np.clip(sepia.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return sepia


def _style_fresh(img: np.ndarray) -> np.ndarray:
    """清新风：亮度提升 + 暖色调 + 饱和度微调"""
    # 1. 亮度提升
    result = np.clip(img.astype(np.float32) + 15, 0, 255).astype(np.uint8)

    # 2. 色温偏暖（R增B减）
    b, g, r = cv2.split(result)
    r = np.clip(r.astype(np.int16) + 8, 0, 255).astype(np.uint8)
    b = np.clip(b.astype(np.int16) - 8, 0, 255).astype(np.uint8)
    result = cv2.merge([b, g, r])

    # 3. 饱和度微调
    hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.2, 0, 255)
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 4. 轻微对比度增强
    result = np.clip(result.astype(np.float32) * 1.05, 0, 255).astype(np.uint8)

    return result


def _style_cyberpunk(img: np.ndarray) -> np.ndarray:
    """赛博朋克：色相偏移 + 对比度增强 + 边缘高亮"""
    # 1. 色相偏移（品红/青色方向）
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 0] = (hsv[:, :, 0] + 30) % 180  # 色相偏移
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.3, 0, 255)  # 饱和度增强
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 2. 对比度增强
    mean = np.mean(result)
    result = np.clip((result.astype(np.float32) - mean) * 1.5 + mean, 0, 255).astype(np.uint8)

    # 3. 边缘高亮（霓虹灯效果）
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edges_dilated = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)

    # 边缘着色为青色/品红
    neon_color = np.zeros((*edges.shape, 3), dtype=np.uint8)
    neon_color[:, :, 0] = edges_dilated * 1  # B (青)
    neon_color[:, :, 2] = edges_dilated * 1  # R (品红)

    result = cv2.add(result, neon_color)

    return result


# ── 风格映射 ─────────────────────────────────────────────────────────────────

STYLE_MAP = {
    "漫画风": _style_manga,
    "油画风": _style_oil_painting,
    "水彩风": _style_watercolor,
    "复古风": _style_vintage,
    "清新风": _style_fresh,
    "赛博朋克": _style_cyberpunk,
}


# ── 公共接口 ─────────────────────────────────────────────────────────────────

def apply_style(image_bytes: bytes, style: str) -> bytes:
    """
    对图片应用指定风格

    Args:
        image_bytes: 原始图片字节数据
        style: 风格名称（漫画风/油画风/水彩风/复古风/清新风/赛博朋克）

    Returns:
        处理后的图片字节数据（JPEG 格式）
    """
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("图片解码失败，可能不是有效的图片格式")

    style_fn = STYLE_MAP.get(style)
    if style_fn is None:
        available = ", ".join(STYLE_MAP.keys())
        raise ValueError(f"未知风格: {style}，可选: {available}")

    logger.info(f"应用风格: {style} (原始尺寸: {img.shape[1]}x{img.shape[0]})")
    result = style_fn(img)

    # 编码为 JPEG
    quality = random.randint(92, 98)
    _, buf = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, quality])

    logger.info(f"风格处理完成: {style}, JPEG质量: {quality}")
    return buf.tobytes()


def get_available_styles() -> list:
    """返回所有可用风格及描述"""
    return [
        {"name": name, "description": STYLE_PRESETS[name]["description"]}
        for name in STYLE_MAP.keys()
    ]
