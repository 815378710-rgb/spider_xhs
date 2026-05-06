"""
完整流程演示：采集 → 改写 → 图片防重
"""
import json
import os
import requests
from loguru import logger
from dotenv import load_dotenv

from apis.xhs_pc_apis import XHS_Apis
from utils.rewrite import create_backend, rewrite_note
from utils.image_processor import process_images


def main():
    load_dotenv()

    # ── 1. 配置 ──────────────────────────────────────────────────────────────
    # AI 改写后端（二选一）
    backend = create_backend(
        "deepseek",
        api_key=os.getenv("DEEPSEEK_API_KEY", "sk-你的key"),
        # model="deepseek-chat"  # 默认
    )
    # 或者用 MiMo：
    # backend = create_backend(
    #     "mimo",
    #     api_key=os.getenv("MIMO_API_KEY", "sk-你的key"),
    # )

    cookies_str = os.getenv("COOKIES", "")
    if not cookies_str:
        logger.error("请在 .env 中配置 COOKIES")
        return

    xhs = XHS_Apis()

    # ── 2. 采集目标笔记 ──────────────────────────────────────────────────────
    note_url = input("请输入要采集的小红书笔记链接: ").strip()
    if not note_url:
        logger.info("使用演示链接...")
        note_url = "https://www.xiaohongshu.com/explore/你的笔记ID?xsec_token=xxx"

    logger.info("正在采集笔记...")
    success, msg, note_info = xhs.get_note_info(note_url, cookies_str)
    if not success:
        logger.error(f"采集失败: {msg}")
        return

    note = note_info['data']['items'][0]['note_card']
    title = note['title']
    desc = note['desc']
    images_raw = [img['info_list'][1]['url'] for img in note.get('image_list', []) if 'info_list' in img]

    logger.info(f"采集成功！标题: {title}")
    logger.info(f"图片数量: {len(images_raw)}")

    # ── 3. AI 改写文案 ────────────────────────────────────────────────────────
    logger.info("正在改写文案...")
    result = rewrite_note(title, desc, backend)

    print("\n" + "=" * 60)
    print("【原标题】", title)
    print("【改写后】", result['title'])
    print("-" * 60)
    print("【原正文】", desc[:200], "..." if len(desc) > 200 else "")
    print("-" * 60)
    print("【改写后】", result['desc'])
    print("=" * 60)

    # ── 4. 下载 + 防重处理图片 ────────────────────────────────────────────────
    if images_raw:
        logger.info(f"正在下载并处理 {len(images_raw)} 张图片...")
        raw_images = []
        for url in images_raw:
            try:
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                raw_images.append(resp.content)
            except Exception as e:
                logger.warning(f"图片下载失败: {e}")

        if raw_images:
            processed_images = process_images(raw_images, level="medium")
            logger.info(f"图片防重处理完成: {len(processed_images)} 张")

            # 保存到本地
            os.makedirs("output/processed_images", exist_ok=True)
            for i, img_bytes in enumerate(processed_images):
                path = f"output/processed_images/image_{i}.jpg"
                with open(path, 'wb') as f:
                    f.write(img_bytes)
                logger.info(f"已保存: {path}")

    # ── 5. 输出改写结果 ────────────────────────────────────────────────────────
    output = {
        "original": {"title": title, "desc": desc},
        "rewritten": {"title": result['title'], "desc": result['desc']},
        "provider": result.get('provider', ''),
        "image_count": len(processed_images) if images_raw else 0,
    }
    os.makedirs("output", exist_ok=True)
    with open("output/rewritten.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info("改写结果已保存到 output/rewritten.json")
    logger.info("全部完成！")


if __name__ == "__main__":
    main()
