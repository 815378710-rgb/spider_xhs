"""
AI味检测与规避模块 — 基于规则的AI痕迹检测 + LLM去AI味
"""
import re
import json
from loguru import logger

# ── AI 高频词汇库 ──────────────────────────────────────────────────────────

AI_WORDS = {
    "综述类": [
        "综上所述", "总而言之", "总的来说", "综上", "总结一下",
        "总而言之", "总的来说", "综上所述", "总结来说",
    ],
    "逻辑连接词": [
        "首先", "其次", "再次", "最后", "最后但同样重要的是",
        "一方面", "另一方面", "不仅如此", "此外", "另外",
        "然而", "不过", "但是", "尽管如此", "与此同时",
    ],
    "AI典型表达": [
        "值得注意的是", "需要指出的是", "值得一提的是",
        "在当今", "在这个时代", "随着科技的发展",
        "不可否认", "毋庸置疑", "显而易见",
        "众所周知", "不言而喻", "事实如此",
        "从本质上讲", "从根本上说", "从某种程度上说",
    ],
    "列举结构": [
        "第一点", "第二点", "第三点",
        "第1点", "第2点", "第3点",
        "第一方面", "第二方面", "第三方面",
    ],
    "空洞修饰": [
        "非常", "十分", "极其", "相当", "颇为",
        "很大程度上", "在一定程度上", "在很大程度上",
    ],
}

# ── AI 典型句式模式 ──────────────────────────────────────────────────────────

AI_PATTERNS = [
    # 过于工整的排比
    (r"不仅.{2,10}而且.{2,10}", "递进排比句式"),
    (r"既.{2,10}又.{2,10}", "并列排比句式"),
    (r"一方面.{2,20}另一方面.{2,20}", "对仗排比句式"),
    # 机械列举
    (r"(?:第一|首先).{5,30}(?:第二|其次).{5,30}(?:第三|再次)", "三段式机械列举"),
    (r"(?:1)[\.、].{5,30}(?:2)[\.、].{5,30}(?:3)[\.、]", "数字编号机械列举"),
    # 过度正式
    (r"本文将.{5,30}进行(?:详细|深入|全面)探讨", "学术论文式开头"),
    (r"以下(?:是|为).{5,30}的(?:详细|具体)说明", "说明文式过渡"),
    # AI 常见开头
    (r"在(?:当今|如今|现在).{2,15}中", "AI 常见时代背景开头"),
    (r"随着.{2,15}的(?:发展|进步|提升)", "AI 常见趋势开头"),
    # AI 常见结尾
    (r"(?:总之|综上|总的来说).{5,30}(?:值得|应该|需要)", "AI 常见总结式结尾"),
]

# ── 缺乏个人色彩的表述 ──────────────────────────────────────────────────────

IMPERSONAL_PATTERNS = [
    (r"用户(?:可以|能够|需要)", "使用「用户」而非「你」或「姐妹们」"),
    (r"消费者(?:可以|能够|需要)", "使用「消费者」而非第一人称"),
    (r"(?:该|此)产品具有", "使用「这个产品」而非「该产品」"),
    (r"(?:该|此)方案(?:能够|可以)", "过于书面化的表述"),
    (r"建议(?:您|用户)", "使用「建议你」而非「建议您」"),
]


# ── 核心检测函数 ──────────────────────────────────────────────────────────────

def detect_ai_trace(text: str) -> dict:
    """
    检测文本中的 AI 痕迹

    Args:
        text: 待检测文本

    Returns:
        {
            "score": 45,  # 0-100，越高 AI 味越浓
            "level": "需要优化",  # 自然/需要优化/AI味明显
            "details": [{"type": "AI高频词汇", "word": "综上所述", "position": 10}],
            "suggestions": ["建议1", "建议2"],
        }
    """
    details = []
    suggestions = []

    # 检测 AI 高频词汇
    for category, words in AI_WORDS.items():
        for word in words:
            start = 0
            while True:
                pos = text.find(word, start)
                if pos == -1:
                    break
                details.append({
                    "type": f"AI高频词汇({category})",
                    "word": word,
                    "position": pos,
                })
                start = pos + len(word)

    # 检测 AI 典型句式
    for pattern, desc in AI_PATTERNS:
        for match in re.finditer(pattern, text):
            details.append({
                "type": f"AI句式({desc})",
                "word": match.group(),
                "position": match.start(),
            })

    # 检测缺乏个人色彩
    for pattern, desc in IMPERSONAL_PATTERNS:
        for match in re.finditer(pattern, text):
            details.append({
                "type": f"缺乏人称({desc})",
                "word": match.group(),
                "position": match.start(),
            })

    # 计算 AI 味分数（0-100，越高越 AI）
    total_len = max(len(text), 1)
    ai_word_count = sum(1 for d in details if "AI高频" in d["type"])
    ai_pattern_count = sum(1 for d in details if "AI句式" in d["type"])

    # 基础分：AI词汇密度
    density_score = min(50, int(ai_word_count / total_len * 5000))
    # 句式分
    pattern_score = min(30, ai_pattern_count * 8)
    # 空洞分
    impersonal_count = sum(1 for d in details if "缺乏人称" in d["type"])
    impersonal_score = min(20, impersonal_count * 5)

    score = min(100, density_score + pattern_score + impersonal_score)

    # 等级
    if score <= 30:
        level = "自然（低AI味）"
    elif score <= 60:
        level = "需要优化"
    else:
        level = "AI味明显，需要深度去AI化"

    # 生成改进建议
    if ai_word_count > 3:
        suggestions.append("减少AI高频词汇（综上所述、首先其次等），用口语化表达替代")
    if ai_pattern_count > 2:
        suggestions.append("打乱过于工整的句式结构，增加长短句交替")
    if impersonal_count > 0:
        suggestions.append("增加第一人称表述（我觉得、我发现、亲测），让内容更有温度")
    if not re.search(r"[！!?]", text):
        suggestions.append("适当加入感叹号和语气词，增加情绪表达")
    if not re.search(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]", text):
        suggestions.append("适当加入emoji，增加视觉节奏感")
    if len(text) > 200 and not re.search(r"\n\n", text):
        suggestions.append("增加段落换行，让排版更轻松，不要一大段到底")

    return {
        "score": score,
        "level": level,
        "details": details,
        "suggestions": suggestions,
    }


def remove_ai_trace(text: str, backend) -> str:
    """
    调用 LLM 去除 AI 痕迹

    Args:
        text: 待处理文本
        backend: LLM 后端实例

    Returns:
        去除 AI 痕迹后的文本
    """
    system_prompt = """你是一个小红书内容润色专家。你的任务是去除文案中的"AI味"，让它读起来像真人写的。

## 去AI味规则
1. 把所有书面化、正式的表达换成口语化、生活化的表达
2. 把"首先/其次/最后"等机械列举换成自然过渡
3. 把"综上所述/总而言之"等AI总结词换成"总之/说白了/一句话"
4. 把"用户/消费者"换成"你/姐妹们"
5. 把过于工整的排比句打散，换成参差不齐的自然句式
6. 增加真实感：加入"我自己的感受是""说实话""亲测"等个人化表达
7. 增加情绪词：绝了、谁懂、救命、太香了、真的会谢
8. 适当加入emoji（但不要满屏都是）
9. 正文段落要有长有短，不要每段都一样长
10. 保留原文的核心信息和卖点，不要改变事实

## 输出
直接输出修改后的文本，不要输出JSON，不要加任何解释。"""

    user_prompt = f"请去除以下文本的AI味，改写成真人写的小红书风格：\n\n{text}"

    try:
        result = backend.chat(system_prompt, user_prompt)
        return result.strip()
    except Exception as e:
        logger.error(f"去AI味失败: {e}")
        return text


def estimate_originality(text: str) -> dict:
    """
    估算文本原创度（基于文本特征分析）

    Returns:
        {
            "score": 85,  # 0-100，越高越原创
            "details": {"unique_ratio": 0.7, "avg_sentence_len": 15, ...},
            "suggestions": ["建议1"],
        }
    """
    # 分句
    sentences = re.split(r'[。！？\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return {"score": 0, "details": {}, "suggestions": ["文本为空"]}

    # 计算特征
    total_chars = len(text)
    unique_chars = len(set(text.replace(" ", "").replace("\n", "")))
    unique_ratio = unique_chars / max(total_chars, 1)

    avg_sentence_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

    # 重复度检测
    word_freq = {}
    for word in re.findall(r'[\u4e00-\u9fff]{2,4}', text):
        word_freq[word] = word_freq.get(word, 0) + 1
    repeated_words = {w: c for w, c in word_freq.items() if c >= 3}
    repeated_ratio = len(repeated_words) / max(len(word_freq), 1)

    # 原创度评分
    score = 50
    # 字符多样性加分
    if unique_ratio > 0.6:
        score += 15
    elif unique_ratio > 0.4:
        score += 8
    # 句子长度适中加分
    if 10 < avg_sentence_len < 40:
        score += 10
    # 重复词少加分
    if repeated_ratio < 0.1:
        score += 15
    elif repeated_ratio < 0.2:
        score += 8
    # 有emoji和感叹号加分
    if re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]', text):
        score += 5
    if re.search(r'[！!?]{2,}', text):
        score += 5

    score = min(100, max(0, score))

    suggestions = []
    if unique_ratio < 0.5:
        suggestions.append("词汇多样性较低，建议使用更多不同的表达")
    if avg_sentence_len > 50:
        suggestions.append("句子偏长，建议拆分成短句，更适合移动端阅读")
    if repeated_ratio > 0.2:
        suggestions.append("重复词汇较多，建议换用同义词或改变表达方式")
    if not re.search(r'[！!?]', text):
        suggestions.append("缺少语气符号，建议适当加入感叹号增加情绪")
    if not re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]', text):
        suggestions.append("缺少emoji，建议适当加入增加视觉节奏")

    return {
        "score": score,
        "details": {
            "unique_ratio": round(unique_ratio, 3),
            "avg_sentence_len": round(avg_sentence_len, 1),
            "repeated_words": len(repeated_words),
            "sentence_count": len(sentences),
        },
        "suggestions": suggestions,
    }
