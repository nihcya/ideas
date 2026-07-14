"""生产环境首次播种脚本：生成最近 N 天的「今日一点」题目。

用途：
- 首次部署到 PostgreSQL 后，初始化题库
- 定时任务失败时手动补题
- 测试 AI 生成功能

用法：
    cd backend
    # 生成今天起未来 7 天的题目
    python -m scripts.seed_spark --days 7

    # 仅生成今天的题目
    python -m scripts.seed_spark --days 1

    # 强制覆盖已存在的题目（慎用）
    python -m scripts.seed_spark --days 7 --force

    # 指定起始日期
    python -m scripts.seed_spark --days 7 --start 2026-07-10

环境变量：
    DATABASE_URL — PostgreSQL 连接串
    DEEPSEEK_API_KEY — DeepSeek API Key（未配置则使用 Mock）
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, timedelta
import sys
from pathlib import Path

# 把 backend 目录加入 sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import init_engine, close_engine, async_session_factory, DB_DIALECT
from models import SparkQuestion
from services.spark_ai_service import generate_and_persist


async def seed_questions(days: int, start: date | None, force: bool) -> None:
    """生成从 start 开始连续 N 天的题目。"""
    await init_engine()

    if DB_DIALECT.startswith("postgresql"):
        print(f"[seed] database: PostgreSQL")
    else:
        print(f"[seed] database: {DB_DIALECT} (注意：本脚本设计用于 PostgreSQL 生产环境)")

    if start is None:
        start = date.today()

    print(f"[seed] generating {days} day(s) of questions, starting {start}")
    print(f"[seed] force overwrite: {force}")

    async with async_session_factory() as session:
        for i in range(days):
            target_date = start + timedelta(days=i)

            if force:
                # 删除已有题目
                await session.execute(
                    delete(SparkQuestion).where(SparkQuestion.date == target_date)
                )
                await session.commit()

            # 检查是否已存在
            existing = await session.execute(
                select(SparkQuestion).where(SparkQuestion.date == target_date)
            )
            if existing.scalar_one_or_none() is not None:
                print(f"[seed] {target_date}: already exists, skipped (use --force to overwrite)")
                continue

            # 生成
            q = await generate_and_persist(session, target_date)
            if q is not None:
                print(f"[seed] {target_date}: OK type={q.type} q={q.question}")
            else:
                print(f"[seed] {target_date}: FAILED")

    await close_engine()
    print("[seed] done")


def main():
    parser = argparse.ArgumentParser(description="生成「今日一点」题目")
    parser.add_argument("--days", type=int, default=7, help="生成天数（默认 7）")
    parser.add_argument("--start", type=str, default=None, help="起始日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的题目")
    args = parser.parse_args()

    start_date = None
    if args.start:
        try:
            start_date = date.fromisoformat(args.start)
        except ValueError:
            print(f"错误：日期格式无效，应为 YYYY-MM-DD，收到 {args.start}")
            sys.exit(1)

    asyncio.run(seed_questions(args.days, start_date, args.force))


if __name__ == "__main__":
    main()
