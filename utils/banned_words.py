"""
违禁词检测模块 — 内置小红书违禁词库 + 分类 + 替换建议
"""
import re
from loguru import logger

# ── 违禁词库（分类存储）─────────────────────────────────────────────────────

BANNED_WORDS_DB = {
    "极限用语": {
        "severity": "critical",
        "words": [
            "最", "最佳", "最好", "最优", "最高", "最低", "最大", "最小",
            "第一", "唯一", "首选", "顶级", "极致", "绝对", "百分百",
            "100%", "全网最低", "史上最强", "史上最便宜", "史上最有效",
            "国家免检", "中国驰名", "极品", "顶级", "领先", "领导品牌",
            "第一品牌", "NO.1", "Top1", "全网第一", "销量第一",
            "全国首创", "全球首发", "填补国内空白", "驰名商标",
            "永久", "万能", "全能", "100%有效", "零风险", "无副作用",
        ],
    },
    "虚假宣传": {
        "severity": "critical",
        "words": [
            "假一赔十", "假一赔百", "假一赔万", "纯天然", "纯植物",
            "无任何添加", "无添加", "零添加", "无化学成分",
            "祖传秘方", "特效", "专柜正品", "正品保证", "假货包赔",
            "一洗白", "一敷就瘦", "立刻见效", "当天见效", "7天见效",
            "一次见效", "3天美白", "7天瘦身", "不反弹", "永不复发",
            "根治", "彻底治愈", "100%治愈", "包治", "药到病除",
            "无效退款", "无效全额退款", "签约治疗", "承诺治愈",
        ],
    },
    "医疗广告": {
        "severity": "critical",
        "words": [
            "治疗", "根治", "药效", "疗效", "治愈", "处方", "药方",
            "特效药", "专治", "主治", "消炎", "杀菌", "抗癌",
            "降血压", "降血糖", "降血脂", "减肥药", "瘦身药",
            "增高", "丰胸", "壮阳", "补肾", "养胃", "排毒",
            "祛痘", "祛斑", "脱敏", "医疗", "药品", "医疗器械",
            "处方药", "非处方药", "OTC", "保健食品",
        ],
    },
    "诱导分享": {
        "severity": "warning",
        "words": [
            "转发", "扩散", "转发有礼", "分享有奖", "集赞",
            "求转发", "求扩散", "朋友圈转发", "转发抽奖",
            "拉人", "邀请好友", "拼团", "砍价", "助力",
            "帮我砍一刀", "分享到群", "分享领红包",
        ],
    },
    "品牌侵权": {
        "severity": "critical",
        "words": [
            "同款", "平替", "大牌同款", "XXX同款", "明星同款",
            "代购正品", "原单", "尾单", "外贸原单", "海关扣押",
            "免税", "免税店", "机场免税", "水货", "A货", "高仿",
            "仿冒", "山寨", "盗版", "仿制品",
        ],
    },
    "绝对化用语": {
        "severity": "warning",
        "words": [
            "最安全", "最有效", "最便宜", "最划算", "最推荐",
            "最好用", "最强", "最火", "最热门", "最畅销",
            "全网最", "史上最强", "没有人比", "无人能敌",
            "无可匹敌", "独一无二", "绝无仅有", "空前绝后",
        ],
    },
    "虚假承诺": {
        "severity": "warning",
        "words": [
            "保证有效", "保证治好", "承诺", "一定", "肯定",
            "绝对能", "保证能", "包你满意", "不满意退款",
            "三天见效", "五天见效", "一周见效", "立即见效",
            "当场见效", "一次就好", "永不复发", "不再反弹",
        ],
    },
}


# ── 核心检测函数 ──────────────────────────────────────────────────────────────

def check_banned_words(text: str) -> dict:
    """
    检测文本中的违禁词

    Args:
        text: 待检测文本

    Returns:
        {
            "found": [{"word": "xxx", "category": "xxx", "position": 5, "severity": "critical/warning/info"}],
            "score": 85,  # 0-100，越高越安全
            "total": 3,
            "by_category": {"极限用语": 1, "虚假宣传": 2},
        }
    """
    found = []
    text_lower = text.lower()

    for category, info in BANNED_WORDS_DB.items():
        severity = info["severity"]
        for word in info["words"]:
            word_lower = word.lower()
            start = 0
            while True:
                pos = text_lower.find(word_lower, start)
                if pos == -1:
                    break
                # 检查是否是更大词的一部分（简单去重）
                found.append({
                    "word": word,
                    "category": category,
                    "position": pos,
                    "severity": severity,
                })
                start = pos + len(word_lower)

    # 按位置排序并去重
    seen = set()
    unique_found = []
    for item in found:
        key = (item["word"], item["position"])
        if key not in seen:
            seen.add(key)
            unique_found.append(item)

    unique_found.sort(key=lambda x: x["position"])

    # 计算安全分（满分100，每个违禁词扣分）
    critical_count = sum(1 for f in unique_found if f["severity"] == "critical")
    warning_count = sum(1 for f in unique_found if f["severity"] == "warning")
    score = max(0, 100 - critical_count * 15 - warning_count * 5)

    # 按类别统计
    by_category = {}
    for f in unique_found:
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1

    return {
        "found": unique_found,
        "score": score,
        "total": len(unique_found),
        "by_category": by_category,
    }


def suggest_replacement(text: str) -> dict:
    """
    为违禁词提供替换建议

    Returns:
        {
            "original": "原文本",
            "suggestions": [{"word": "xxx", "category": "xxx", "replacements": ["替代词1", "替代词2"], "severity": "xxx"}],
            "cleaned_text": "替换后的文本",
        }
    """
    # 替换建议映射
    REPLACEMENT_MAP = {
        # 极限用语
        "最好": ["很不错", "挺好", "值得推荐"],
        "最佳": ["优质", "推荐", "优选"],
        "第一": ["领先", "热门", "人气高"],
        "唯一": ["少有的", "稀缺的", "特别的"],
        "顶级": ["高端", "优质", "精品"],
        "极致": ["非常好", "很棒", "出色"],
        "绝对": ["确实", "真的很", "非常"],
        "百分百": ["非常", "很", "特别"],
        "100%": ["非常", "很"],
        "全网最低": ["性价比很高", "价格友好", "很划算"],
        "史上最强": ["非常强大", "很厉害", "超好用"],
        "NO.1": ["热门", "人气", "爆款"],
        # 虚假宣传
        "纯天然": ["天然成分", "植物萃取", "自然配方"],
        "纯植物": ["植物系", "植萃", "草本"],
        "无任何添加": ["成分简单", "配方温和", "少添加"],
        "零添加": ["无额外添加", "成分精简"],
        "假一赔十": ["正品保障", "品质保证", "假货包退"],
        "祖传秘方": ["独家配方", "特色配方", "经典配方"],
        "特效": ["效果好", "很好用", "表现出色"],
        "一次见效": ["用后感受明显", "效果不错", "体验很好"],
        "不反弹": ["效果持久", "稳定", "持续有效"],
        "根治": ["改善", "缓解", "调理"],
        "无效退款": ["售后保障", "不满意可退"],
        # 绝对化用语
        "最安全": ["很安全", "安全性高", "温和安全"],
        "最有效": ["效果好", "很有效", "效果明显"],
        "最便宜": ["价格实惠", "很划算", "性价比高"],
        "最推荐": ["强烈推荐", "很推荐", "值得入手"],
        "最好用": ["很好用", "使用感好", "体验不错"],
        # 医疗广告
        "治疗": ["改善", "缓解", "调理"],
        "治愈": ["恢复", "好转", "改善"],
        "特效药": ["好用的产品", "有效的产品"],
        "消炎": ["舒缓", "镇静", "安抚"],
        "减肥": ["塑形", "纤体", "管理身材"],
        "祛痘": ["战痘", "痘肌护理", "控油净痘"],
        "祛斑": ["淡斑", "均匀肤色", "提亮"],
        # 品牌侵权
        "同款": ["类似款", "同类型", "相似款"],
        "平替": ["性价比替代", "类似产品"],
        "高仿": ["致敬款", "相似款"],
    }

    result = check_banned_words(text)
    suggestions = []
    cleaned = text

    for item in result["found"]:
        word = item["word"]
        replacements = REPLACEMENT_MAP.get(word, ["(请自行替换)"])
        suggestions.append({
            "word": word,
            "category": item["category"],
            "replacements": replacements,
            "severity": item["severity"],
            "position": item["position"],
        })

    # 生成清理后文本（按位置倒序替换，避免位置偏移）
    for item in sorted(result["found"], key=lambda x: x["position"], reverse=True):
        word = item["word"]
        replacements = REPLACEMENT_MAP.get(word, [])
        if replacements:
            cleaned = cleaned[:item["position"]] + replacements[0] + cleaned[item["position"] + len(word):]

    return {
        "original": text,
        "suggestions": suggestions,
        "cleaned_text": cleaned,
    }
