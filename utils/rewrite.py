"""
AI 文案改写模块
支持 DeepSeek / MiMo 大模型，可扩展
"""
import json
import os
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
        resp = requests.post(url, headers=headers, json=body, timeout=60)
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
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        if resp.status_code == 401:
            headers.pop("Authorization", None)
            headers["api-key"] = self.api_key
            resp = requests.post(url, headers=headers, json=body, timeout=120)
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
        resp = requests.post(url, headers=headers, json=body, timeout=60)
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
}


def rewrite_note(title: str, desc: str, backend: LLMBackend,
                 extra_instructions: str = None, style: str = "保持原风格") -> dict:
    """
    改写一篇笔记的标题和正文

    Args:
        title: 原标题
        desc: 原正文
        backend: LLM 后端实例
        extra_instructions: 额外的改写指令（可选，可与 style 叠加）
        style: 改写风格（保持原风格/种草带货风/干货教程风/情绪共鸣风/测评对比风/清单合集风）

    Returns:
        {"title": "改写后标题", "desc": "改写后正文", "provider": "xxx", "style": "xxx"}
    """
    # 组装 user prompt
    user_prompt = f"请改写以下小红书笔记：\n\n【原标题】{title}\n\n【原正文】{desc}"

    # 叠加风格指令
    style_instruction = STYLE_INSTRUCTIONS.get(style)
    if style_instruction:
        user_prompt += f"\n\n{style_instruction}"

    # 叠加用户自定义额外指令
    if extra_instructions:
        user_prompt += f"\n\n【用户额外要求】{extra_instructions}"

    logger.info(f"正在使用 {backend.name} 改写文案 (风格: {style})...")
    raw = backend.chat(SYSTEM_PROMPT, user_prompt)

    # 解析 JSON 响应
    result = _parse_response(raw)
    result["provider"] = backend.name
    result["style"] = style
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
    import re
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
