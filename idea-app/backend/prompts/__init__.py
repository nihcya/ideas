"""AI 提示词模板 — 单一来源。

按 TECH_CONSTRAINTS.md 第6节目录结构要求外置。
deepseek_client.py 与未来扩展的审核/演化模块统一从这里导入。
"""
from .templates import (
    COLLIDE_PROMPT,
    EVOLVE_PROMPT,
    AUDIT_PROMPT,
    SAMPER_ANGLES,
    SPARK_QUESTION_PROMPT,
    SPARK_QUESTION_TYPES,
)

__all__ = [
    "COLLIDE_PROMPT",
    "EVOLVE_PROMPT",
    "AUDIT_PROMPT",
    "SAMPER_ANGLES",
    "SPARK_QUESTION_PROMPT",
    "SPARK_QUESTION_TYPES",
]
