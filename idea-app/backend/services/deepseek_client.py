"""大模型客户端 — OpenAI 兼容协议，含 Mock 兜底。

优先级：per-user 配置 > 全局 .env 配置 > Mock 模式。
支持任何 OpenAI 兼容端点：DeepSeek / OpenAI / Kimi / 通义 / 智谱等。
提示词统一从 prompts 模块导入，避免硬编码漂移。
"""
import json
import random
from typing import Any

from openai import AsyncOpenAI

from config import settings
from prompts import (
    COLLIDE_PROMPT,
    EVOLVE_PROMPT,
    AUDIT_PROMPT,
    SAMPER_ANGLES,
)


def _resolve_config(
    user_api_url: str | None = None,
    user_api_key: str | None = None,
) -> tuple[str | None, str | None, bool]:
    """解析出当前调用应使用的 (api_url, api_key, is_mock)。

    优先级：per-user 配置 > 全局配置 > Mock。
    返回的 url 可能是 None（表示用客户端默认）。
    """
    url = (user_api_url or "").strip() or settings.deepseek_base_url
    key = (user_api_key or "").strip() or settings.deepseek_api_key
    is_mock = not bool(key)
    return url, key, is_mock


def _get_client(
    api_url: str | None = None,
    api_key: str | None = None,
) -> AsyncOpenAI:
    """按 (url, key) 构造客户端。不缓存，避免跨用户污染。"""
    kwargs: dict[str, Any] = {
        "api_key": api_key or "not-configured",
        "timeout": 30.0,
        "max_retries": 2,
    }
    if api_url:
        kwargs["base_url"] = api_url
    return AsyncOpenAI(**kwargs)


# ============================================================
# Mock 数据（无 API Key 时使用）
# ============================================================

_MOCK_COLLIDE_SUGGESTIONS = [
    {
        "content": "将两者的核心机制融合：建立城市级的『时间-技能』双轨账本，老人的生活经验积分可兑换年轻人的维修服务，年轻人的服务时长又转化为对老人的陪伴基金。",
        "type": "practical",
    },
    {
        "content": "引入『游戏化设计』视角：把社区互助做成开放式沙盒，每个老人是一个NPC，年轻人通过完成老人的真实需求任务解锁社区故事线，时间银行变成游戏内货币。",
        "type": "cross_domain",
    },
    {
        "content": "反转主客体：让老人成为服务的发起方而不是接收方。老人发布自己擅长的技能（讲故事、做菜、修旧物），年轻人付费预约，老人用收入雇佣其他年轻人做体力活。",
        "type": "unconventional",
    },
]


def _mock_evolve_variants(content: str, angle: str) -> list[dict]:
    """根据角度生成 mock 变体。"""
    templates = {
        "substitute": [
            ("把原点子里的『人力』替换为『AI调度』，老人通过语音发起需求，AI自动匹配最近的志愿者。", "near"),
            ("把『一对一服务』替换为『群组互助』，5个老人+5个年轻人组成互助小组，轮流服务。", "medium"),
            ("把『线下社区』替换为『移动房车』，服务站点每天迁移到不同小区，覆盖更广。", "bold"),
        ],
        "adapt": [
            ("借鉴GitHub的Fork机制：每个老人的需求是一个Repo，年轻人Fork后做变体实现。", "near"),
            ("借鉴维基百科的编辑机制：服务记录是公开可编辑的，社区共同维护老人档案。", "medium"),
            ("借鉴开源社区的PR机制：年轻人提交『服务提案』，社区评审后合并执行。", "bold"),
        ],
        "modify": [
            ("放大服务时长：单次服务从1小时延长到3小时，深化代际交流质量。", "near"),
            ("缩小服务规模：聚焦独居老人，每位志愿者长期绑定1位老人，建立深度关系。", "medium"),
            ("完全重构：把『服务』变成『共创』，老人和年轻人一起做产品/写书/拍视频。", "bold"),
        ],
        "put_to_other_use": [
            ("同样的机制用到乡村：城市志愿者远程服务乡村留守老人。", "near"),
            ("用到企业内部：员工用业余时间服务公司周边社区，转化为公司ESG积分。", "medium"),
            ("用到监狱：服刑人员通过服务老人获得减刑积分，重建社会连接。", "bold"),
        ],
        "eliminate": [
            ("去掉『时间账本』：服务不记账，纯靠善意流动，看是否能形成自发循环。", "near"),
            ("去掉『社区边界』：全国老人和志愿者跨区匹配，需求-能力全网调度。", "medium"),
            ("去掉『人』：训练AI陪伴机器人承担80%的陪伴需求，人只负责20%的深度连接。", "bold"),
        ],
        "reverse": [
            ("让老人服务年轻人：老人教年轻人做菜、修旧物、讲故事，年轻人付费。", "near"),
            ("让『被需要』变成商品：老人发布『我需要被需要』的需求，年轻人付费来获得被感激的体验。", "medium"),
            ("完全反转：年轻人是被服务的对象，老人是服务提供者，重新定义『谁在帮助谁』。", "bold"),
        ],
    }
    items = templates.get(angle, templates["substitute"])
    return [{"content": c, "distance": d} for c, d in items]


async def call_collide_ai(
    content_a: str,
    content_b: str,
    user_api_url: str | None = None,
    user_api_key: str | None = None,
) -> dict[str, Any]:
    """碰撞两个点子，返回 3 个结合方案。"""
    url, key, is_mock = _resolve_config(user_api_url, user_api_key)
    if is_mock:
        suggestions = list(_MOCK_COLLIDE_SUGGESTIONS)
        random.shuffle(suggestions)
        return {"suggestions": suggestions}

    prompt = COLLIDE_PROMPT.format(content_a=content_a, content_b=content_b)

    client = _get_client(url, key)
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


async def call_evolve_ai(
    content: str,
    angle: str,
    angle_desc: str,
    user_api_url: str | None = None,
    user_api_key: str | None = None,
) -> dict[str, Any]:
    """演化一个点子，返回 3 个变体。"""
    url, key, is_mock = _resolve_config(user_api_url, user_api_key)
    if is_mock:
        return {"variants": _mock_evolve_variants(content, angle)}

    prompt = EVOLVE_PROMPT.format(content=content, angle=angle, angle_desc=angle_desc)

    client = _get_client(url, key)
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


async def call_audit_ai(content: str) -> dict[str, Any]:
    """AI 内容审核。

    审核调用强制使用全局 .env 配置，不接受用户自定义 API 配置，
    避免用户通过自定义 endpoint 绕过审核（SSRF + 审核绕过防护）。
    """
    # 审核强制走全局配置：不传 user 参数
    url, key, is_mock = _resolve_config()
    if is_mock:
        if len(content.strip()) < 2:
            return {"pass": False, "reason": "内容过短"}
        return {"pass": True, "reason": ""}

    prompt = AUDIT_PROMPT.format(content=content)

    client = _get_client(url, key)
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=200,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


# SAMPER_ANGLES 已从 prompts 模块导入，无需在此重复定义
