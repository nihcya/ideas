"""每日一题 AI 生成服务

负责调用 DeepSeek（或任何 OpenAI 兼容端点）动态生成发散性思维题目。

设计要点：
1. **去重**：查询最近 7 天的题目，拼入 prompt 防止 AI 重复
2. **随机化**：从 4 种类型中随机选取，避免类型固化
3. **降级**：无 API Key 时使用 Mock 题库，保证服务可用
4. **重试**：AI 返回格式异常或内容不合规时重试（最多 2 次）
5. **原子写入**：调用方负责事务，本服务只返回 (question, type)

调用方职责：
- 在事务中先 SELECT 检查当日是否已有题目
- 调用本服务生成
- 写入 spark_questions 表（依赖 date 字段唯一约束兜底竞态）
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import SparkQuestion
from prompts import SPARK_QUESTION_PROMPT, SPARK_QUESTION_TYPES


# ============================================================
# Mock 题库（无 API Key 时使用，保证服务可用）
# ============================================================
# 每种类型预置若干题，随机抽取。开发/测试环境必需。
_MOCK_QUESTIONS: dict[str, list[str]] = {
    "random_word": [
        "回形针",
        "纽扣",
        "鞋带",
        "便利贴",
        "橡皮筋",
        "钥匙扣",
        "衣架",
        "卷尺",
    ],
    "reverse_question": [
        "如果没有人需要睡觉会怎样？",
        "如果颜色能发出声音会怎样？",
        "如果每个人只能记住昨天会怎样？",
        "如果城市没有名字会怎样？",
        "如果镜子能照见未来会怎样？",
    ],
    "analogy": [
        "用『水母漂浮』设计一个城市交通系统",
        "用『竹节生长』设计一个个人成长工具",
        "用『蝙蝠回声』设计一个空间导航产品",
        "用『蜘蛛结网』设计一个社交网络",
    ],
    "constraint": [
        "在不能用文字的前提下，设计一个日记 App",
        "在只能使用一种颜色的前提下，设计一个品牌标识系统",
        "在每人每天只能说 10 句话的前提下，设计一个沟通工具",
        "在不能用电子屏幕的前提下，设计一个学习工具",
    ],
}


def _pick_random_type() -> str:
    """从 4 种类型中随机选一种。"""
    return random.choice(list(SPARK_QUESTION_TYPES.keys()))


async def _get_recent_questions(
    db: AsyncSession,
    days: int = 7,
    today: Optional[date] = None,
) -> list[str]:
    """获取最近 N 天已出过的题目文本，用于去重。"""
    if today is None:
        today = date.today()
    start = today - timedelta(days=days)
    result = await db.execute(
        select(SparkQuestion.question).where(
            SparkQuestion.date > start,
            SparkQuestion.date <= today,
        ).order_by(SparkQuestion.date.desc())
    )
    return [row[0] for row in result.fetchall()]


def _format_recent_questions(questions: list[str]) -> str:
    """格式化最近题目列表，拼入 prompt。"""
    if not questions:
        return "（暂无历史题目）"
    return "\n".join(f"- {q}" for q in questions)


def _mock_generate(q_type: str, recent: list[str]) -> tuple[str, str]:
    """Mock 生成：从预置题库随机抽，避免与最近题目重复。"""
    pool = _MOCK_QUESTIONS.get(q_type, _MOCK_QUESTIONS["random_word"])
    # 过滤掉最近 7 天出现过的
    available = [q for q in pool if q not in recent]
    if not available:
        # 全用过了就允许重复（极端情况）
        available = pool
    question = random.choice(available)
    return question, q_type


async def generate_question(
    db: AsyncSession,
    today: Optional[date] = None,
    forced_type: Optional[str] = None,
) -> tuple[str, str]:
    """生成一道每日一题。

    Args:
        db: 数据库 session（用于查询最近题目做去重）
        today: 目标日期，默认今天
        forced_type: 强制指定类型，None 则随机

    Returns:
        (question, type) — 题目文本与类型标识
    """
    if today is None:
        today = date.today()

    q_type = forced_type if forced_type in SPARK_QUESTION_TYPES else _pick_random_type()
    recent = await _get_recent_questions(db, days=7, today=today)

    # 无 API Key 走 Mock
    if not settings.is_deepseek_configured:
        return _mock_generate(q_type, recent)

    # 调用 DeepSeek
    from services.deepseek_client import _get_client  # 复用客户端构造逻辑

    type_desc = SPARK_QUESTION_TYPES[q_type]
    prompt = SPARK_QUESTION_PROMPT.format(
        q_type=q_type,
        type_desc=type_desc,
        recent_questions=_format_recent_questions(recent),
    )

    # 重试机制：AI 偶尔返回非 JSON 或字段缺失
    last_error: Optional[str] = None
    for attempt in range(2):
        try:
            client = _get_client(settings.deepseek_base_url, settings.deepseek_api_key)
            resp = await client.chat.completions.create(
                model=settings.deepseek_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            question = str(data.get("question", "")).strip()
            returned_type = str(data.get("type", q_type)).strip()

            # 校验
            if not question or len(question) > 100:
                raise ValueError(f"题目为空或过长: len={len(question)}")
            if returned_type not in SPARK_QUESTION_TYPES:
                returned_type = q_type  # 修正异常类型

            # 轻度去重：完全相同的题目重试
            if question in recent and attempt == 0:
                last_error = "与最近题目重复"
                continue

            return question, returned_type
        except Exception as e:
            last_error = str(e)
            print(f"[spark_ai] generate attempt {attempt + 1} failed: {e}")
            continue

    # AI 全部失败 → Mock 兜底，保证服务可用
    print(f"[spark_ai] AI generation failed ({last_error}), falling back to mock")
    return _mock_generate(q_type, recent)


async def generate_and_persist(
    db: AsyncSession,
    today: Optional[date] = None,
    forced_type: Optional[str] = None,
) -> Optional[SparkQuestion]:
    """生成题目并写入数据库。

    依赖 spark_questions.date 的唯一约束兜底并发：
    若两个 worker 同时生成同一天的题目，后者会因 IntegrityError 失败。
    失败后尝试在同 session 查询；若查不到（隔离级别问题），返回 None，
    调用方可在新 session 中重试 SELECT。

    Returns:
        写入成功返回 SparkQuestion；并发冲突且查询不到时返回 None
    """
    if today is None:
        today = date.today()

    # 二次检查：避免无谓的 AI 调用
    existing = await db.execute(
        select(SparkQuestion).where(SparkQuestion.date == today)
    )
    existing_q = existing.scalar_one_or_none()
    if existing_q is not None:
        return existing_q

    question, q_type = await generate_question(db, today, forced_type)
    new_q = SparkQuestion(
        date=today,
        question=question,
        type=q_type,
    )
    db.add(new_q)
    try:
        await db.commit()
    except Exception as e:
        print(f"[spark_ai] persist failed (likely concurrent insert): {e}")
        await db.rollback()
        # 尝试查询已提交的记录（可能在其他事务中已成功）
        try:
            result = await db.execute(
                select(SparkQuestion).where(SparkQuestion.date == today)
            )
            return result.scalar_one_or_none()
        except Exception:
            return None
    await db.refresh(new_q)
    return new_q
