"""
图片防重处理模块
基础防重：尺寸调整 + 微调色温/亮度/对比度 + 轻微裁切 + 随机旋转
依赖：opencv-python, numpy (已在 requirements.txt)
"""
import random
import math
from io import BytesIO

import cv2
import numpy as np
from loguru import logger


# ── 核心处理函数 ──────────────────────────────────────────────────────────────

class ImageProcessor:
    """
    图片防重处理器

    所有操作都可单独开关，参数可配置。
    处理后的图片从视觉上看几乎没区别，但像素级指纹完全不同。
    """

    def __init__(self,
                 resize_ratio: tuple = (0.9, 1.1),
                 rotate_range: tuple = (-2.0, 2.0),
                 crop_margin: float = 0.02,
                 brightness_range: tuple = (-10, 10),
                 contrast_range: tuple = (0.95, 1.05),
                 saturation_range: tuple = (0.9, 1.1),
                 temperature_range: tuple = (-8, 8),
                 noise_level: int = 3,
                 jpeg_quality_range: tuple = (90, 98),
                 enable_resize: bool = True,
                 enable_rotate: bool = True,
                 enable_crop: bool = True,
                 enable_color: bool = True,
                 enable_noise: bool = True):
        """
        Args:
            resize_ratio: 宽高缩放范围，如 (0.9, 1.1) 表示 ±10%
            rotate_range: 旋转角度范围（度），如 (-2, 2)
            crop_margin: 边缘裁切比例，如 0.02 表示每边裁 2%
            brightness_range: 亮度调整范围（-255~255）
            contrast_range: 对比度倍数范围
            saturation_range: 饱和度倍数范围
            temperature_range: 色温偏移范围（正偏暖，负偏冷）
            noise_level: 高斯噪声标准差（越大越明显）
            jpeg_quality_range: JPEG 压缩质量范围
            enable_*: 各功能开关
        """
        self.resize_ratio = resize_ratio
        self.rotate_range = rotate_range
        self.crop_margin = crop_margin
        self.brightness_range = brightness_range
        self.contrast_range = contrast_range
        self.saturation_range = saturation_range
        self.temperature_range = temperature_range
        self.noise_level = noise_level
        self.jpeg_quality_range = jpeg_quality_range
        self.enable_resize = enable_resize
        self.enable_rotate = enable_rotate
        self.enable_crop = enable_crop
        self.enable_color = enable_color
        self.enable_noise = enable_noise

    def process(self, image_bytes: bytes) -> bytes:
        """
        对图片进行防重处理

        Args:
            image_bytes: 原始图片的字节数据

        Returns:
            处理后的图片字节数据（JPEG 格式）
        """
        # 解码
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("图片解码失败，可能不是有效的图片格式")

        h, w = img.shape[:2]
        logger.debug(f"原始尺寸: {w}x{h}")

        # 先检测原始图的内容区域
        orig_content = self._detect_content_bbox(img)
        orig_content_area = orig_content[2] * orig_content[3] if orig_content else 0

        # 按顺序处理
        if self.enable_resize:
            img = self._resize(img)

        if self.enable_crop:
            img = self._crop(img)

        if self.enable_rotate:
            img = self._rotate(img)

        if self.enable_color:
            img = self._adjust_color(img)

        if self.enable_noise:
            img = self._add_noise(img)

        # 安全检查：验证处理后内容是否保留
        new_content = self._detect_content_bbox(img)
        new_content_area = new_content[2] * new_content[3] if new_content else 0

        if orig_content_area > 0:
            preservation_ratio = new_content_area / orig_content_area
            if preservation_ratio < 0.3:
                logger.warning(f"内容保留不足 ({preservation_ratio:.1%})，回退亮度/对比度调整")
                # 回退到更安全的参数重新处理
                img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
                if self.enable_resize:
                    img = self._resize(img)
                if self.enable_crop:
                    img = self._crop(img)
                if self.enable_rotate:
                    img = self._rotate(img)
                # 使用更保守的颜色调整
                img = self._safe_adjust_color(img)

        # 编码为 JPEG（随机质量）
        quality = random.randint(*self.jpeg_quality_range)
        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])

        h2, w2 = img.shape[:2]
        logger.debug(f"处理后尺寸: {w2}x{h2}, JPEG质量: {quality}")
        return buf.tobytes()

    def process_file(self, input_path: str, output_path: str = None) -> str:
        """
        处理图片文件

        Args:
            input_path: 输入图片路径
            output_path: 输出路径（默认在原文件名后加 _processed）

        Returns:
            输出文件路径
        """
        if output_path is None:
            name, ext = input_path.rsplit('.', 1)
            output_path = f"{name}_processed.{ext}"

        with open(input_path, 'rb') as f:
            data = f.read()

        result = self.process(data)

        with open(output_path, 'wb') as f:
            f.write(result)

        logger.info(f"图片处理完成: {input_path} → {output_path}")
        return output_path

    # ── 内部处理方法 ──────────────────────────────────────────────────────────

    def _resize(self, img: np.ndarray) -> np.ndarray:
        """随机缩放"""
        h, w = img.shape[:2]
        ratio_w = random.uniform(*self.resize_ratio)
        ratio_h = random.uniform(*self.resize_ratio)
        new_w = max(1, int(w * ratio_w))
        new_h = max(1, int(h * ratio_h))
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    def _crop(self, img: np.ndarray) -> np.ndarray:
        """边缘轻微裁切（智能避让内容区域）"""
        h, w = img.shape[:2]
        margin = self.crop_margin

        # 先检测内容区域，避免裁掉内容
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)
        coords = cv2.findNonZero(thresh)

        if coords is not None:
            cx, cy, cw, ch = cv2.boundingRect(coords)
            # 内容占图像比例
            content_area_ratio = (cw * ch) / (w * h)
            # 如果内容占比超过60%，只在内容区域外裁切
            if content_area_ratio > 0.6:
                # 计算可裁切的最大范围（内容边缘之外）
                max_top = max(0, cy - 2)
                max_bottom = max(0, h - (cy + ch) - 2)
                max_left = max(0, cx - 2)
                max_right = max(0, w - (cx + cw) - 2)
                # 取可裁范围和 margin 的较小值
                top = int(min(max_top, h * random.uniform(0, margin)))
                bottom = int(min(max_bottom, h * random.uniform(0, margin)))
                left = int(min(max_left, w * random.uniform(0, margin)))
                right = int(min(max_right, w * random.uniform(0, margin)))
            else:
                top = int(h * random.uniform(margin * 0.3, margin * 0.8))
                bottom = int(h * random.uniform(margin * 0.3, margin * 0.8))
                left = int(w * random.uniform(margin * 0.3, margin * 0.8))
                right = int(w * random.uniform(margin * 0.3, margin * 0.8))
        else:
            # 没有检测到内容，正常裁切
            top = int(h * random.uniform(margin, margin * 1.5))
            bottom = int(h * random.uniform(margin, margin * 1.5))
            left = int(w * random.uniform(margin, margin * 1.5))
            right = int(w * random.uniform(margin, margin * 1.5))

        # 确保裁完还有内容
        if top + bottom >= h - 2 or left + right >= w - 2:
            return img
        return img[top:h - bottom, left:w - right]

    def _rotate(self, img: np.ndarray) -> np.ndarray:
        """随机微旋转（使用白色填充避免反射白边冲淡内容）"""
        angle = random.uniform(*self.rotate_range)
        h, w = img.shape[:2]
        center = (w / 2, h / 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        # 旋转后裁掉黑边：稍微扩大画布
        cos_a = abs(math.cos(math.radians(angle)))
        sin_a = abs(math.sin(math.radians(angle)))
        new_w = int(h * sin_a + w * cos_a)
        new_h = int(h * cos_a + w * sin_a)
        matrix[0, 2] += (new_w - w) / 2
        matrix[1, 2] += (new_h - h) / 2
        # 使用白色填充（BORDER_CONSTANT with white=255），
        # 避免 BORDER_REFLECT_101 将白边反射进内容区域
        rotated = cv2.warpAffine(img, matrix, (new_w, new_h),
                                  borderMode=cv2.BORDER_CONSTANT,
                                  borderValue=(255, 255, 255))
        # 裁回原始比例（从中心裁）
        rh, rw = rotated.shape[:2]
        y_start = (rh - h) // 2
        x_start = (rw - w) // 2
        return rotated[max(0, y_start):y_start + h, max(0, x_start):x_start + w]

    def _adjust_color(self, img: np.ndarray) -> np.ndarray:
        """调整亮度、对比度、饱和度、色温（自适应：检测图像亮度后智能调整）"""
        # 检测图像整体亮度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        # 亮度自适应：已经很亮的图（>200）减少亮度增加，偏暗的图可多加
        brightness = random.uniform(*self.brightness_range)
        if mean_brightness > 200:
            brightness = min(0, brightness)
        elif mean_brightness < 80:
            brightness = max(brightness, 5)

        # 使用 int16 避免 uint8 溢出（旧版 numpy 的 np.full_like 会静默溢出负值）
        img = np.clip(img.astype(np.int16) + brightness, 0, 255).astype(np.uint8)

        # 对比度自适应：高亮图像减少对比度增强
        contrast = random.uniform(*self.contrast_range)
        if mean_brightness > 200:
            contrast = min(contrast, 1.0)
        img = np.clip(img.astype(np.float32) * contrast, 0, 255).astype(np.uint8)

        # 饱和度（转 HSV 调整 S 通道）
        saturation = random.uniform(*self.saturation_range)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
        img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        # 色温（BGR 通道偏移）
        temperature = random.uniform(*self.temperature_range)
        if mean_brightness > 200:
            temperature = temperature * 0.5
        b, g, r = cv2.split(img)
        r = np.clip(r.astype(np.int16) + temperature, 0, 255).astype(np.uint8)
        b = np.clip(b.astype(np.int16) - temperature, 0, 255).astype(np.uint8)
        img = cv2.merge([b, g, r])

        return img

    def _add_noise(self, img: np.ndarray) -> np.ndarray:
        """添加轻微高斯噪声"""
        sigma = random.uniform(0.5, self.noise_level)
        noise = np.random.normal(0, sigma, img.shape).astype(np.float32)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return img

    def _detect_content_bbox(self, img: np.ndarray):
        """检测图像中文字/内容的边界框，返回 (x, y, w, h) 或 None"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 用自适应阈值检测暗色文字（适合白底图片）
        _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
        # 轻微膨胀，连接断裂的文字笔画
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=1)
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return None
        x, y, w, h = cv2.boundingRect(coords)
        return (x, y, w, h)

    def _safe_adjust_color(self, img: np.ndarray) -> np.ndarray:
        """安全的颜色调整：只做微小的色温偏移和饱和度调整，不动亮度和对比度"""
        # 只做色温偏移（范围缩小一半）
        temperature = random.uniform(*self.temperature_range) * 0.3
        b, g, r = cv2.split(img)
        r = np.clip(r.astype(np.int16) + temperature, 0, 255).astype(np.uint8)
        b = np.clip(b.astype(np.int16) - temperature, 0, 255).astype(np.uint8)
        img = cv2.merge([b, g, r])

        # 微调饱和度
        saturation = random.uniform(0.97, 1.03)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
        img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        return img


# ── 预设方案 ──────────────────────────────────────────────────────────────────

def light_processor() -> ImageProcessor:
    """轻度处理：肉眼几乎看不出区别，但指纹已改变"""
    return ImageProcessor(
        resize_ratio=(0.97, 1.03),
        rotate_range=(-1.0, 1.0),
        crop_margin=0.01,
        brightness_range=(-5, 5),
        contrast_range=(0.98, 1.02),
        saturation_range=(0.95, 1.05),
        temperature_range=(-5, 5),
        noise_level=2,
        jpeg_quality_range=(92, 98),
    )


def medium_processor() -> ImageProcessor:
    """中度处理：推荐方案，防重效果好且不影响观感"""
    return ImageProcessor(
        resize_ratio=(0.92, 1.08),
        rotate_range=(-2.0, 2.0),
        crop_margin=0.02,
        brightness_range=(-10, 10),
        contrast_range=(0.95, 1.05),
        saturation_range=(0.9, 1.1),
        temperature_range=(-8, 8),
        noise_level=3,
        jpeg_quality_range=(90, 96),
    )


def heavy_processor() -> ImageProcessor:
    """重度处理：更激进的防重，肉眼可能略有感知"""
    return ImageProcessor(
        resize_ratio=(0.88, 1.12),
        rotate_range=(-3.0, 3.0),
        crop_margin=0.03,
        brightness_range=(-15, 15),
        contrast_range=(0.92, 1.08),
        saturation_range=(0.85, 1.15),
        temperature_range=(-12, 12),
        noise_level=5,
        jpeg_quality_range=(85, 95),
    )


# ── 快捷函数 ──────────────────────────────────────────────────────────────────

def process_image(image_bytes: bytes, level: str = "medium") -> bytes:
    """
    快捷函数：处理单张图片

    Args:
        image_bytes: 图片字节数据
        level: 处理强度 "light" | "medium" | "heavy"

    Returns:
        处理后的图片字节
    """
    presets = {
        "light": light_processor,
        "medium": medium_processor,
        "heavy": heavy_processor,
    }
    factory = presets.get(level)
    if not factory:
        raise ValueError(f"未知处理级别: {level}，可选: {list(presets.keys())}")
    return factory().process(image_bytes)


def process_images(image_list: list, level: str = "medium") -> list:
    """
    批量处理图片

    Args:
        image_list: 图片字节列表
        level: 处理强度

    Returns:
        处理后的图片字节列表
    """
    processor = {
        "light": light_processor,
        "medium": medium_processor,
        "heavy": heavy_processor,
    }.get(level, medium_processor)()
    return [processor.process(img) for img in image_list]


# ── 使用示例 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python image_processor.py <图片路径> [输出路径] [light|medium|heavy]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    level = sys.argv[3] if len(sys.argv) > 3 else "medium"

    proc = {"light": light_processor, "medium": medium_processor, "heavy": heavy_processor}[level]()
    result_path = proc.process_file(input_path, output_path)
    print(f"处理完成: {result_path}")
