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
        """边缘轻微裁切"""
        h, w = img.shape[:2]
        margin = self.crop_margin
        # 每边随机裁 margin% ~ margin*1.5%
        top = int(h * random.uniform(margin, margin * 1.5))
        bottom = int(h * random.uniform(margin, margin * 1.5))
        left = int(w * random.uniform(margin, margin * 1.5))
        right = int(w * random.uniform(margin, margin * 1.5))
        # 确保裁完还有内容
        if top + bottom >= h - 2 or left + right >= w - 2:
            return img
        return img[top:h - bottom, left:w - right]

    def _rotate(self, img: np.ndarray) -> np.ndarray:
        """随机微旋转"""
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
        rotated = cv2.warpAffine(img, matrix, (new_w, new_h),
                                  borderMode=cv2.BORDER_REFLECT_101)
        # 裁回原始比例（从中心裁）
        rh, rw = rotated.shape[:2]
        y_start = (rh - h) // 2
        x_start = (rw - w) // 2
        return rotated[max(0, y_start):y_start + h, max(0, x_start):x_start + w]

    def _adjust_color(self, img: np.ndarray) -> np.ndarray:
        """调整亮度、对比度、饱和度、色温"""
        # 亮度
        brightness = random.uniform(*self.brightness_range)
        img = cv2.add(img, np.full_like(img, brightness, dtype=np.uint8))

        # 对比度
        contrast = random.uniform(*self.contrast_range)
        img = np.clip(img.astype(np.float32) * contrast, 0, 255).astype(np.uint8)

        # 饱和度（转 HSV 调整 S 通道）
        saturation = random.uniform(*self.saturation_range)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
        img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        # 色温（BGR 通道偏移）
        temperature = random.uniform(*self.temperature_range)
        # 偏暖：R 增 G 微增 B 减；偏冷反之
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
