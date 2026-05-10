"""
AI 文案改写模块
支持 DeepSeek / MiMo 大模型，可扩展
支持 Agent 辩论机制：多Agent并行改写 → 评审打分 → 输出最优方案
"""
import json
import os
import re
import threading
from abc import ABC, abstractmethod
from loguru import logger

try:
    import requests
except ImportError:
    raise ImportError("请安装 requests: pip install requests")


# ── 抽象后端 ──────────────────────────────────────────────────────────────────

class LLMBackend(ABC):
    """大模型后端抽象接口"""

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


# ── DeepSeek ──────────────────────────────────────────────────────────────────

class DeepSeekBackend(LLMBackend):
    """DeepSeek API 后端（兼容 OpenAI 格式）

    可用模型：
        - deepseek-v3 (DeepSeek V3, 默认)
        - deepseek-v4 (DeepSeek V4)
        - deepseek-chat (旧版别名，等同于 v3)
    """

    def __init__(self, api_key: str, model: str = "deepseek-v3",
                 base_url: str = "https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return f"DeepSeek/{self.model}"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 2000,
        }
        resp = requests.request('POST', url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


# ── MiMo（小米大模型，兼容 OpenAI 格式）────────────────────────────────────────

class MiMoBackend(LLMBackend):
    """MiMo 大模型后端（小米，兼容 OpenAI 格式）

    可用模型：
        - mimo-v2-pro (MiMo V2 Pro, 旗舰推理)
        - mimo-v2-flash (MiMo V2 Flash, 轻量快速)

    API 文档: https://platform.xiaomimimo.com/
    Base URL: https://token-plan-cn.xiaomimimo.com/v1
    认证头: api-key: xxx （不是 Authorization: Bearer）
    """

    def __init__(self, api_key: str, model: str = "mimo-v2-pro",
                 base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return f"MiMo/{self.model}"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        # 小米官方兼容 OpenAI 格式，优先用 Bearer，401 时自动降级 api-key
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 1.0,
            "max_tokens": 2000,
        }
        # 推理模型需要更多 token（大量 token 用于思考过程）
        body["max_tokens"] = 8000
        resp = requests.request('POST', url, headers=headers, json=body, timeout=120)
        if resp.status_code == 401:
            headers.pop("Authorization", None)
            headers["api-key"] = self.api_key
            resp = requests.request('POST', url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        # 推理模型 content 可能为空，取 reasoning_content
        return (msg.get("content") or msg.get("reasoning_content") or "").strip()


# ── 通用 OpenAI 兼容后端（兜底扩展）───────────────────────────────────────────

class OpenAICompatBackend(LLMBackend):
    """通用 OpenAI 兼容后端，任何兼容 /v1/chat/completions 的服务都能用"""

    def __init__(self, api_key: str, model: str, base_url: str, name: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._name = name or f"OpenAICompat/{model}"

    @property
    def name(self) -> str:
        return self._name

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 2000,
        }
        resp = requests.request('POST', url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


# ── 后端工厂 ──────────────────────────────────────────────────────────────────

def create_backend(provider: str, api_key: str, **kwargs) -> LLMBackend:
    """
    工厂函数，按名称创建后端

    用法:
        backend = create_backend("deepseek", api_key="sk-xxx")
        backend = create_backend("mimo", api_key="sk-xxx")
        backend = create_backend("openai_compat", api_key="sk-xxx",
                                 model="xxx", base_url="https://...")
    """
    providers = {
        "deepseek": DeepSeekBackend,
        "mimo": MiMoBackend,
    }
    cls = providers.get(provider.lower())
    if cls:
        return cls(api_key=api_key, **kwargs)
    if provider.lower() in ("openai_compat", "custom"):
        return OpenAICompatBackend(api_key=api_key, **kwargs)
    raise ValueError(f"不支持的后端: {provider}，可选: {list(providers.keys())} / openai_compat")


def create_backend_from_env() -> LLMBackend:
    """
    从环境变量读取配置创建后端

    环境变量:
        LLM_PROVIDER   = deepseek | mimo | openai_compat
        LLM_API_KEY    = sk-xxx
        LLM_MODEL      = (可选) 模型名
        LLM_BASE_URL   = (可选) 自定义 base_url
    """
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise ValueError("请在 .env 中设置 LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    kwargs = {}
    if model:
        kwargs["model"] = model
    if base_url:
        kwargs["base_url"] = base_url
    return create_backend(provider, api_key, **kwargs)


# ── 改写引擎 ──────────────────────────────────────────────────────────────────

# ── 小红书爆款改写系统提示词 ──────────────────────────────────────────────────
# 基于小红书算法逻辑和爆款内容拆解，嵌入以下核心机制：
# 1. 标题爆款公式（数字、反差、身份、紧迫、好奇、权威）
# 2. 前3行 hook 逻辑（决定 80% 的完读率）
# 3. 关键词自然植入（提升搜索排名）
# 4. 互动引导（提升评论/收藏/点赞率）
# 5. 段落节奏（短段落 + emoji 点缀，符合移动端阅读习惯）

SYSTEM_PROMPT = """你是一个小红书百万粉级别的内容运营专家。你的任务是改写笔记文案，让它具备爆款潜质。

## 核心改写原则

### 1. 标题爆款公式（必须选一种）
- **数字型**：「3招搞定XX」「XX只需9.9元」「第2个绝了」
- **反差型**：「从XX到XX，我只做了一件事」「被低估的XX」
- **身份型**：「打工人必看」「学生党福音」「30岁才知道的事」
- **紧迫型**：「后悔没早知道」「再不XX就晚了」「别再花冤枉钱」
- **好奇型**：「原来XX才是YY的关键」「为什么XX反而更XX」
- **权威型**：「成分党实测」「皮肤科医生推荐」「用了5年的XX」

标题15-25字，带1-2个emoji，必须制造点击欲。

### 2. 正文结构（决定完读率和互动率）
- **开头Hook（前3行）**：用痛点/利益/好奇心/反问句立刻抓住注意力，这是生死线
- **正文干货**：每段3-5行，每段一个核心点，短句为主，穿插真实感受
- **关键词植入**：自然融入3-5个搜索热词（品类词+功效词+人群词），不要堆砌
- **互动收尾**：用提问/投票/求分享引导评论，用「先收藏再说」引导收藏

### 3. 语气和风格
- 像跟闺蜜/朋友聊天，不是写广告文案
- 用「姐妹们」「谁懂」「救命」「绝了」等小红书高频口语词
- emoji 在关键位置点缀（段首、重点词前后），每段1-3个，不要满屏都是
- 正文200-800字，太短没干货，太长没人看

### 4. 改写红线
- 核心卖点、价格、优惠信息不能丢
- 至少70%的文字要和原文不同（换句式、换措辞、换结构）
- 不要编造产品没有的功能或数据
- 不要用「推荐」「安利」等可能触发广告审核的敏感词，改用「自用分享」「回购清单」

## 输出格式
严格输出JSON，不要输出其他任何内容：
{"title": "改写后的标题", "desc": "改写后的正文"}"""


# ── 风格模板 ──────────────────────────────────────────────────────────────────
# 每种风格对应不同的额外指令，叠加在基础 SYSTEM_PROMPT 上

STYLE_INSTRUCTIONS = {
    "保持原风格": None,

    "种草带货风": """【种草带货专项指令】
- 标题必须包含价格或折扣信息，制造「不买就亏」的紧迫感
- 正文突出「自用回购」「空瓶分享」的真实感，不要写成广告
- 用对比法：「之前用XX踩坑，换了这个之后...」
- 收尾用「趁活动赶紧囤」「链接放评论区」引导行动
- 关键词侧重：价格词（平价/学生党/性价比）+ 功效词""",

    "干货教程风": """【干货教程专项指令】
- 标题用「教程」「攻略」「手把手」等词，配合数字
- 正文用步骤式结构（Step 1/2/3 或 第一步/第二步）
- 每个步骤配一个具体操作说明，不要空泛
- 收尾用「学会了吗」「你们觉得哪个步骤最关键」引导互动
- 关键词侧重：教程词（怎么/如何/教程/攻略）+ 品类词""",

    "情绪共鸣风": """【情绪共鸣专项指令】
- 标题用感叹句或反问句，触发情绪共鸣（「谁懂啊」「救命」「太真实了」）
- 正文用故事化叙述，有起承转合，像讲自己的经历
- 适当加入「踩坑经历」增加真实感和共情
- 收尾用「有同感的姐妹举手」「你们有没有过这种经历」引导评论
- 关键词侧重：情绪词（避雷/踩坑/后悔/真香）+ 人群词""",

    "测评对比风": """【测评对比专项指令】
- 标题用「测评」「对比」「实测」等词，配合「XX vs XX」
- 正文用对比结构：列出2-3个维度（价格/效果/使用感）逐一对比
- 用表格或分点式呈现，方便截图收藏
- 给出明确结论：「综合来看，XX更适合XX人群」
- 收尾用「你们更倾向哪个」「评论区投票」引导互动
- 关键词侧重：对比词（vs/对比/哪个好/区别）+ 品牌词""",

    "清单合集风": """【清单合集专项指令】
- 标题用数字+品类：「XX个必入的XX」「XX合集」「XX清单」
- 正文用编号列表，每个item用1-2句话说清核心卖点
- 每个item带价格区间和适合人群
- 适当加「私藏」「回购N次」等词增加信任感
- 收尾用「你们还有什么好用的XX推荐吗」引导评论
- 关键词侧重：清单词（合集/清单/必入/好物）+ 品类词""",

    "日常分享风": """【日常分享专项指令】
- 标题用轻松口语化表达，像发朋友圈一样自然（「最近入手的XX」「终于找到好用的XX」）
- 正文像跟朋友聊天，语气随意亲切，不要太正式
- 分享真实的使用场景和生活片段，弱化营销感
- 适当加入生活化的 emoji（☕️🏠🌿），不要太商业
- 收尾用「你们平时怎么用的」「有同款吗」拉近距离
- 关键词侧重：生活词（日常/通勤/居家/出门）+ 品类词""",

    "避雷种草风": """【避雷种草专项指令】
- 标题用「避雷」「踩坑」「别买」等反向词汇制造好奇（「XX千万别买！除非你...」）
- 正文先说1-2个真实缺点（增加可信度），再转折说优点
- 用「但是！」「没想到」「真香」制造反差感
- 语气要真诚坦率，像闺蜜之间的真心话
- 收尾用「你们踩过类似的坑吗」引导评论
- 关键词侧重：避雷词（避雷/踩坑/后悔/真香）+ 品类词""",

    "懒人速成风": """【懒人速成专项指令】
- 标题强调简单快速（「3步搞定XX」「1分钟学会XX」「懒人必看」）
- 正文极简步骤化，每步一句话说清楚
- 不废话不啰嗦，直接上干货
- 用「省流版」「一图看懂」等关键词
- 收尾用「学会了吗」「这么简单还不试试」
- 关键词侧重：效率词（懒人/速成/快速/简单/一步）+ 品类词""",

    "学生党省钱风": """【学生党省钱专项指令】
- 标题突出价格优势（「学生党平价XX」「XX只要9.9」「穷学生的福音」）
- 正文重点标注价格和性价比，对比同类产品
- 加入学生身份认同（「宿舍里都在用」「食堂钱省下来买这个」）
- 分享省钱小技巧和优惠信息
- 收尾用「学生党互推」「还有更便宜的吗」引导互动
- 关键词侧重：价格词（平价/学生党/便宜/省钱/性价比）+ 人群词""",

    "情感故事风": """【情感故事专项指令】
- 标题用故事化悬念（「用了XX之后，我的生活变了...」「那个改变我的XX」）
- 正文用第一人称叙述，有起承转合的完整故事
- 融入个人情感和心路历程，让读者产生代入感
- 产品植入要自然，像故事的一部分而不是广告
- 收尾用「你们有过类似的经历吗」引发共鸣
- 关键词侧重：情感词（改变/治愈/温暖/回忆）+ 品类词""",

    "专业成分党": """【专业成分党专项指令】
- 标题用专业术语+数据（「含XX%烟酰胺的XX实测」「成分解析：XX到底值不值」）
- 正文列出核心成分及其功效，用数据说话
- 对比成分浓度和配方表，体现专业度
- 用「成分表解读」「配方分析」等专业词汇
- 收尾用「成分党来聊聊」「你们看重哪些成分」引导讨论
- 关键词侧重：成分词（成分/配方/浓度/功效/成分表）+ 品牌词""",
}


def _get_ratio_instruction(ratio: int) -> str:
    """根据改写比例返回对应的 prompt 指令"""
    if ratio <= 30:
        return "【改写比例：轻微润色（约30%）】\n保留原文的结构和大部分措辞，仅优化语句通顺度、调整语序、点缀emoji。标题可以微调，正文主体内容保持原样。"
    elif ratio <= 50:
        return "【改写比例：平衡改写（约50%，推荐）】\n保持核心意思不变，改写约一半的文字。优化标题吸引力和开头hook，调整段落节奏，换用更小红书化的表达。"
    elif ratio <= 70:
        return "【改写比例：深度改写（约70%）】\n大幅调整文章结构和措辞，仅保留核心卖点和关键数据（价格、成分、效果等）。标题必须重写，正文用全新的叙述方式。"
    else:
        return "【改写比例：全面重塑（约90%）】\n仅保留产品核心信息（品名、价格、核心功效），其余完全重新创作。标题、开头、正文结构、结尾全部重写，像写一篇全新的笔记。"


def rewrite_note(title: str, desc: str, backend: LLMBackend,
                 extra_instructions: str = None, style: str = "保持原风格",
                 ratio: int = 50) -> dict:
    """
    改写一篇笔记的标题和正文

    Args:
        title: 原标题
        desc: 原正文
        backend: LLM 后端实例
        extra_instructions: 额外的改写指令（可选，可与 style 叠加）
        style: 改写风格（12种可选）
        ratio: 改写比例（30-90），控制改写幅度

    Returns:
        {"title": "改写后标题", "desc": "改写后正文", "provider": "xxx", "style": "xxx", "ratio": 50}
    """
    # 组装 user prompt
    user_prompt = f"请改写以下小红书笔记：\n\n【原标题】{title}\n\n【原正文】{desc}"

    # 叠加改写比例指令
    ratio_instruction = _get_ratio_instruction(ratio)
    user_prompt += f"\n\n{ratio_instruction}"

    # 叠加风格指令
    style_instruction = STYLE_INSTRUCTIONS.get(style)
    if style_instruction:
        user_prompt += f"\n\n{style_instruction}"

    # 叠加用户自定义额外指令
    if extra_instructions:
        user_prompt += f"\n\n【用户额外要求】{extra_instructions}"

    logger.info(f"正在使用 {backend.name} 改写文案 (风格: {style}, 比例: {ratio}%)...")
    raw = backend.chat(SYSTEM_PROMPT, user_prompt)

    # 解析 JSON 响应
    result = _parse_response(raw)
    result["provider"] = backend.name
    result["style"] = style
    result["ratio"] = ratio
    logger.info(f"改写完成: {result['title'][:30]}...")
    return result


def rewrite_batch(notes: list, backend: LLMBackend,
                  extra_instructions: str = None) -> list:
    """
    批量改写笔记

    Args:
        notes: [{"title": "...", "desc": "..."}, ...]
        backend: LLM 后端实例
        extra_instructions: 额外指令

    Returns:
        [{"title": "改写后", "desc": "改写后", "provider": "xxx"}, ...]
    """
    results = []
    for i, note in enumerate(notes):
        logger.info(f"改写进度: {i + 1}/{len(notes)}")
        try:
            result = rewrite_note(note["title"], note["desc"], backend, extra_instructions)
            results.append(result)
        except Exception as e:
            logger.error(f"第 {i + 1} 篇改写失败: {e}")
            results.append({"title": note["title"], "desc": note["desc"],
                            "provider": "FAILED", "error": str(e)})
    return results


def _parse_response(raw: str) -> dict:
    """解析模型返回的 JSON，带容错"""
    # 尝试直接解析
    try:
        data = json.loads(raw)
        if "title" in data and "desc" in data:
            return data
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            if "title" in data and "desc" in data:
                return data
        except json.JSONDecodeError:
            pass

    # 尝试找第一个 { ... }
    m = re.search(r'\{[^{}]*"title"[^{}]*"desc"[^{}]*\}', raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            return data
        except json.JSONDecodeError:
            pass

    # 兜底：把整个输出当正文，标题留空
    logger.warning("模型返回格式异常，使用兜底方案")
    return {"title": "", "desc": raw}


# ── Agent 辩论系统 ────────────────────────────────────────────────────────────
# 3个专业Agent并行改写 → 评审Agent打分 → 输出最优方案

AGENT_PROFILES = {
    "A": {
        "name": "爆款猎手",
        "emoji": "🔥",
        "system_prompt": """你是一个小红书爆款内容专家，专攻标题党和情绪驱动。你的目标是让笔记获得最高点击率和互动率。

核心能力：
- 标题制造强烈点击欲（数字冲击、情绪词、悬念感）
- 前3行hook必须让人停不下来
- 大量使用小红书高频情绪词（绝了/谁懂/救命/太香了/后悔没早买）
- 互动引导强烈（评论区见/你们觉得呢/姐妹们冲）

输出格式：严格JSON {"title": "改写后的标题", "desc": "改写后的正文"}"""
    },
    "B": {
        "name": "干货专家",
        "emoji": "📚",
        "system_prompt": """你是一个小红书干货内容专家，专攻信息密度和实用价值。你的目标是让笔记获得高收藏率和搜索排名。

核心能力：
- 标题精准包含搜索关键词（教程/攻略/步骤/方法）
- 正文结构清晰，步骤化呈现，方便截图收藏
- 信息密度高，每句话都有实际价值
- 关键词布局精准，覆盖品类词+功效词+人群词

输出格式：严格JSON {"title": "改写后的标题", "desc": "改写后的正文"}"""
    },
    "C": {
        "name": "人设博主",
        "emoji": "💫",
        "system_prompt": """你是一个小红书人设博主内容专家，专攻真实感和粉丝信任。你的目标是让笔记建立长期粉丝粘性。

核心能力：
- 标题像朋友分享（最近发现/自用回购/终于找到）
- 正文有个人故事和真实体验感
- 语气自然不做作，像跟闺蜜聊天
- 适度分享缺点增加可信度，真诚推荐而非硬广

输出格式：严格JSON {"title": "改写后的标题", "desc": "改写后的正文"}"""
    },
}

JUDGE_SYSTEM_PROMPT = """你是一个小红书内容评审专家。你需要从3个版本中选出综合最优的一个。

## 评分维度（每项1-10分）
1. **标题吸引力**：是否有点击欲？是否制造了好奇心？
2. **内容质量**：信息量、可读性、结构清晰度
3. **互动引导**：是否有评论/收藏/点赞的引导设计
4. **关键词布局**：搜索关键词是否自然融入
5. **风格一致性**：与目标改写风格的匹配程度

## 输出格式
严格输出JSON，不要输出其他内容：
{
  "winner": "A或B或C",
  "scores": {
    "A": {"title": 8, "content": 7, "interaction": 9, "keywords": 7, "style": 8, "total": 39},
    "B": {"title": 7, "content": 9, "interaction": 7, "keywords": 8, "style": 7, "total": 38},
    "C": {"title": 8, "content": 8, "interaction": 8, "keywords": 7, "style": 9, "total": 40}
  },
  "reasoning": "版本C综合评分最高，人设真实感强，互动引导自然..."
}"""


def _agent_rewrite_single(agent_key: str, title: str, desc: str, style: str,
                          ratio: int, backend: LLMBackend, results: dict):
    """单个Agent改写（线程回调）"""
    profile = AGENT_PROFILES[agent_key]
    try:
        user_prompt = f"请改写以下小红书笔记：\n\n【原标题】{title}\n\n【原正文】{desc}"
        ratio_instruction = _get_ratio_instruction(ratio)
        user_prompt += f"\n\n{ratio_instruction}"
        style_instruction = STYLE_INSTRUCTIONS.get(style)
        if style_instruction:
            user_prompt += f"\n\n{style_instruction}"

        logger.info(f"[Agent {agent_key}:{profile['name']}] 开始改写...")
        raw = backend.chat(profile["system_prompt"], user_prompt)
        result = _parse_response(raw)
        result["agent"] = agent_key
        result["agent_name"] = profile["name"]
        result["agent_emoji"] = profile["emoji"]
        results[agent_key] = result
        logger.info(f"[Agent {agent_key}:{profile['name']}] 改写完成: {result['title'][:30]}...")
    except Exception as e:
        logger.error(f"[Agent {agent_key}:{profile['name']}] 改写失败: {e}")
        results[agent_key] = {"title": title, "desc": desc, "agent": agent_key,
                               "agent_name": profile["name"], "agent_emoji": profile["emoji"],
                               "error": str(e)}


def rewrite_with_debate(title: str, desc: str, backend: LLMBackend,
                        style: str = "保持原风格", ratio: int = 50) -> dict:
    """
    Agent 辩论改写：3个Agent并行改写 → 评审Agent打分 → 输出最优方案

    Args:
        title: 原标题
        desc: 原正文
        backend: LLM 后端实例
        style: 改写风格
        ratio: 改写比例

    Returns:
        {
            "winner": {...},          # 最优方案（含title, desc, agent_name等）
            "alternatives": [...],    # 其他两个方案
            "scores": {...},          # 各Agent评分
            "reasoning": "...",       # 评审理由
            "all_versions": [...]     # 3个完整版本
        }
    """
    logger.info(f"Agent 辩论启动 (风格: {style}, 比例: {ratio}%)")

    # Phase 1: 3个Agent并行改写
    results = {}
    threads = []
    for key in ["A", "B", "C"]:
        t = threading.Thread(
            target=_agent_rewrite_single,
            args=(key, title, desc, style, ratio, backend, results)
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=120)  # 最多等2分钟

    # 检查是否有足够结果
    successful = [k for k in ["A", "B", "C"] if "error" not in results.get(k, {})]
    if len(successful) < 2:
        logger.warning(f"辩论降级：仅 {len(successful)} 个Agent成功，退回单次改写")
        # 降级：取第一个成功的，或走普通改写
        if successful:
            fallback = results[successful[0]]
            fallback["provider"] = backend.name
            fallback["style"] = style
            fallback["ratio"] = ratio
            fallback["debate_degraded"] = True
            return {"winner": fallback, "alternatives": [], "scores": {},
                    "reasoning": "辩论降级：部分Agent失败，使用最佳单次结果",
                    "all_versions": list(results.values())}
        else:
            raise RuntimeError("所有Agent改写均失败")

    # Phase 2: 评审Agent打分
    logger.info("评审Agent开始打分...")
    versions_text = ""
    for key in ["A", "B", "C"]:
        r = results.get(key, {})
        versions_text += f"\n\n【版本{key} - {r.get('agent_name', key)}】\n标题：{r.get('title', '')}\n正文：{r.get('desc', '')}"

    judge_prompt = f"请评审以下3个改写版本，目标风格：{style}，改写比例：{ratio}%\n{versions_text}"

    try:
        judge_raw = backend.chat(JUDGE_SYSTEM_PROMPT, judge_prompt)
        # 尝试解析评审结果
        judge_result = _parse_judge_response(judge_raw)
        logger.info(f"评审完成，获胜者: {judge_result.get('winner', 'A')}")
    except Exception as e:
        logger.error(f"评审失败: {e}，使用默认获胜者A")
        judge_result = {"winner": "A", "scores": {}, "reasoning": f"评审异常: {e}"}

    winner_key = judge_result.get("winner", "A")
    winner = results.get(winner_key, results.get("A"))
    winner["provider"] = backend.name
    winner["style"] = style
    winner["ratio"] = ratio

    alternatives = [results[k] for k in ["A", "B", "C"]
                    if k != winner_key and "error" not in results.get(k, {})]

    return {
        "winner": winner,
        "alternatives": alternatives,
        "scores": judge_result.get("scores", {}),
        "reasoning": judge_result.get("reasoning", ""),
        "all_versions": list(results.values()),
    }


def _parse_judge_response(raw: str) -> dict:
    """解析评审Agent的JSON响应"""
    try:
        data = json.loads(raw)
        if "winner" in data:
            return data
    except json.JSONDecodeError:
        pass

    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            if "winner" in data:
                return data
        except json.JSONDecodeError:
            pass

    # 找包含 "winner" 的 JSON 块
    m = re.search(r'\{[^{}]*"winner"[^{}]*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    logger.warning("评审响应解析失败，使用默认值")
    return {"winner": "A", "scores": {}, "reasoning": "评审响应格式异常"}


# ── 使用示例 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # 方式1：从环境变量自动创建
    # backend = create_backend_from_env()

    # 方式2：直接指定（DeepSeek V3 或 V4）
    backend = create_backend(
        "deepseek",
        api_key="sk-你的key",
        model="deepseek-v3"   # 或 "deepseek-v4"
    )
    # MiMo V2 Pro 或 V2 Flash：
    # backend = create_backend("mimo", api_key="你的key", model="mimo-v2-pro")

    # 改写单篇
    result = rewrite_note(
        title="夏天必入的防晒霜！SPF50+清爽不油腻",
        desc="姐妹们！这款防晒霜真的绝了！SPF50+ PA++++的高倍防晒，上脸一点都不油腻，成膜超快...",
        backend=backend,
        extra_instructions="语气更活泼一点，多加emoji"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
