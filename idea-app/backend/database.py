"""数据库引擎 + Session 工厂"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text, select

from config import settings


def _resolve_database_url() -> tuple[str, str]:
    """返回 (主URL, 数据库类型)。"""
    return settings.database_url, settings.database_url.split("+", 1)[0].split(":", 1)[0]


DATABASE_URL, DB_DIALECT = _resolve_database_url()

# SQLite 需要特殊参数
engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if DB_DIALECT.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = False
    if "+aiosqlite" not in DATABASE_URL and "sqlite" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
    DB_DIALECT = "sqlite"
else:
    # PostgreSQL 生产参数：连接池调优，避免高并发时连接耗尽 / 请求堆积
    # - pool_size: 常驻连接数（每个 worker）
    # - max_overflow: 突发可临时扩容的连接数
    # - pool_timeout: 等连接的最长时间，超时抛异常而非无限排队
    # - pool_recycle: 主动回收连接，避免 PG/中间件 idle 超时断连
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    })

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _try_connect_postgres() -> bool:
    """尝试连接 PostgreSQL，失败返回 False。"""
    if not DB_DIALECT.startswith("postgresql"):
        return False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[database] PostgreSQL connect failed: {e}")
        return False


async def init_engine() -> None:
    """初始化引擎：尝试连接PG，失败则根据 APP_ENV 决定降级或退出。

    生产环境（APP_ENV=prod）下 PG 不可用直接抛异常，
    避免 SQLite 静默降级导致并发写锁死和数据丢失。
    """
    global engine, async_session_factory, DATABASE_URL, DB_DIALECT
    if DB_DIALECT.startswith("postgresql"):
        ok = await _try_connect_postgres()
        if not ok:
            # 生产环境：拒绝降级
            if settings.app_env == "prod":
                raise RuntimeError(
                    "[database] PostgreSQL unavailable in prod environment. "
                    "Refusing to fall back to SQLite (concurrency unsafe). "
                    "Check DATABASE_URL / PG status."
                )
            # dev/test 环境允许 SQLite 兜底
            print(f"[database] PostgreSQL unavailable, falling back to SQLite (dev mode).")
            DATABASE_URL = settings.database_url_fallback
            if "sqlite" in DATABASE_URL and "+aiosqlite" not in DATABASE_URL:
                DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
            DB_DIALECT = "sqlite"
            engine = create_async_engine(DATABASE_URL, echo=False)
            async_session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )

    # SQLite 模式下自动建表 + 插入初始数据
    if DB_DIALECT == "sqlite":
        await _init_sqlite_schema()
    elif DB_DIALECT.startswith("postgresql"):
        # PG 环境：确保当日「今日一点」题目存在（AI 兜底）
        # 定时任务正常情况下会在 00:05 预生成，这里只是双保险
        await _ensure_today_spark_question()


async def _init_sqlite_schema() -> None:
    """SQLite 模式：自动建表 + 插入初始数据。"""
    # 延迟导入避免循环依赖
    from models import Base  # noqa: F401
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[database] SQLite schema created via SQLAlchemy create_all")
    # create_all does not ALTER existing tables; apply additive column upgrades before queries.
    await _migrate_sqlite_columns()

    # 插入初始数据（幂等）
    await _seed_initial_data()


async def _seed_initial_data() -> None:
    """插入初始 PGC 数据 + 题库 + 违禁词（幂等）。"""
    from models import (
        User, Idea, SparkQuestion, BannedWord,
    )
    from services.color_pool import COLOR_POOL
    import random

    async with async_session_factory() as session:
        # 检查是否已初始化
        result = await session.execute(select(User).where(User.username == "dianzi_pgc"))
        if result.scalar_one_or_none() is None:
            # 创建 PGC 系统账号
            pgc_user = User(
                username="dianzi_pgc",
                password_hash="$2b$12$placeholder_hash_for_pgc_account_not_for_login_xxxxxx",
                bio="点子App官方精选PGC内容池",
            )
            session.add(pgc_user)
            await session.flush()  # 拿到 id

            pgc_ideas = [
                ("用蚁群算法优化城市配送路径，让快递员像蚂蚁觅食一样自适应分工，拥堵时段自动分流", "#FF6B6B"),
                ("用蜘蛛网结构设计独居老人监测网：每个邻居是一个节点，异常自动震动相邻节点", "#4ECDC4"),
                ("社区时间银行：用一小时陪伴换一小时修理，老人的经验和年轻人的体力互换", "#FFE66D"),
                ("把电梯按钮设计成'目的地+人格'模式，让同楼层的人自然相遇聊天", "#FF8E72"),
                ("用地铁噪音发电：地铁站台铺压电材料，列车刹车的振动转化为电能回馈电网", "#6EC5E9"),
                ("小区快递柜变成'漂流书站'：取件时留下你最近读过的一本书的便签", "#C5E8A0"),
                ("把跑步机连到电网，健身房会员的运动量直接折算电费返还", "#7FD6A1"),
                ("超市临期食品自动拍卖系统：距离过期越近价格越低，最后1小时1折起拍", "#FFB347"),
                ("用蜂巢结构设计共享办公隔间：六边形空间可拼可拆，按小时租用", "#B5A8E8"),
                ("把医院候诊椅改成单车式，等待时可以发电+锻炼+缓解焦虑", "#83A6ED"),
                ("城市'雨水花园'计划：每栋楼的阳台接雨水管，垂直绿化自动浇灌", "#A8D8D8"),
                ("用漂流瓶模式做'陌生人书签'：在书里夹你写的一句话，下个读者扫码联系你", "#FF9EBB"),
                ("把红绿灯倒计时变成小游戏：等灯时多人PK心算，赢家积分换地铁券", "#C9B1FF"),
                ("社区厨房共享：自家厨房闲置时段开放预订，邻居付费使用，平台抽成", "#FFB6C1"),
                ("用'愿望树'模式做社区互助：把需求写在卡片挂树上，路人摘卡完成", "#D4A5A5"),
                ("把废弃共享单车改造成社区菜园支架：车轮当攀爬架，车筐当种植箱", "#FF6B6B"),
                ("用'图书馆借工具'模式做DIY工具站：电钻/梯子/缝纫机按日租借", "#4ECDC4"),
                ("把老人晨练广场变成'代际操场'：早6-8点老人用，晚5-7点年轻人陪老人练", "#FFE66D"),
                ("用'地铁盲盒'做城市探索App：每天推荐一个陌生地铁站，给3个探索任务", "#FF8E72"),
                ("把冰箱贴变成家庭情绪温度计：每天家人选一个表情贴上，情绪异常自动关怀", "#6EC5E9"),
                ("用'许愿池'模式做城市微更新：市民投币选择改造点，众筹满额政府配资启动", "#C5E8A0"),
                ("把公司OKR改成'游戏成就墙'：每个目标是一枚徽章，团队完成自动亮灯", "#7FD6A1"),
                ("用'植物社交'做笔友App：两个人共养一盆远程植物，浇水需要互相写信触发", "#FFB347"),
                ("把图书馆书架装重力感应：哪本书被拿起最多自动上'本周热搜'墙", "#B5A8E8"),
                ("用'声音明信片'模式：录30秒环境音+一句话寄给陌生人，对方回寄一段", "#83A6ED"),
                ("把小区停车位变成'夜间露营地'：白天停车，晚上预约给城市露营爱好者", "#A8D8D8"),
                ("用'技能扑克'模式做人才匹配：每人把技能画成扑克牌，组队按花色搭配", "#FF9EBB"),
                ("把咖啡渣循环做成'种子杯'：杯子用咖啡渣压制，喝完埋土里长出花", "#C9B1FF"),
                ("用'地铁车厢主题日'做城市文化：周一是图书车厢，周三是宠物车厢", "#FFB6C1"),
                ("把老人智能手机课程改成'逆向师徒'：年轻人教老人用手机，老人教年轻人做菜", "#D4A5A5"),
            ]
            for content, color in pgc_ideas:
                session.add(Idea(
                    content=content,
                    color_hex=color,
                    source="pgc",
                    author_id=pgc_user.id,
                    border_style="none",
                    ai_assisted=False,
                ))
            print(f"[database] Seeded {len(pgc_ideas)} PGC ideas")

        # 30 天今日一点题库
        result = await session.execute(select(SparkQuestion).limit(1))
        if result.scalar_one_or_none() is None:
            from datetime import date, timedelta
            today = date.today()
            questions = [
                ("如果手机没有屏幕会怎样？", "reverse_question"),
                ("用『蜘蛛网』为独居老人设计一个产品", "analogy"),
                ("电梯", "random_word"),
                ("如果所有人只能拥有一件物品会怎样？", "reverse_question"),
                ("用『蜂巢』设计一个共享办公空间", "analogy"),
                ("在不能用手机的前提下，设计一个让陌生人交流的产品", "constraint"),
                ("垃圾桶", "random_word"),
                ("如果时间是货币会怎样？", "reverse_question"),
                ("用『蘑菇』设计一个城市农业产品", "analogy"),
                ("在3天没电的前提下，设计一个娱乐产品", "constraint"),
                ("雨伞", "random_word"),
                ("如果城市没有红绿灯会怎样？", "reverse_question"),
                ("用『蚂蚁觅食』优化快递配送", "analogy"),
                ("在只允许使用纸质的前提下，设计一个日程管理工具", "constraint"),
                ("楼梯", "random_word"),
                ("如果学校没有考试会怎样？", "reverse_question"),
                ("用『树根共生』设计一个社区互助系统", "analogy"),
                ("在不能讲话的前提下，设计一个团队协作工具", "constraint"),
                ("镜子", "random_word"),
                ("如果金钱不能购买物质会怎样？", "reverse_question"),
                ("用『候鸟迁徙』设计一个内容推荐机制", "analogy"),
                ("在所有人共用一个日历的前提下，设计一个约会安排工具", "constraint"),
                ("绳结", "random_word"),
                ("如果记忆可以被交易会怎样？", "reverse_question"),
                ("用『珊瑚礁』设计一个生态社区", "analogy"),
                ("在只能用图像不能用文字的前提下，设计一个日记App", "constraint"),
                ("钥匙", "random_word"),
                ("如果每个人只能活到30岁会怎样？", "reverse_question"),
                ("用『萤火虫闪烁』设计一个城市夜景交互装置", "analogy"),
                ("在不能重复使用任何材料的前提下，设计一个餐具", "constraint"),
            ]
            for i, (q, t) in enumerate(questions):
                session.add(SparkQuestion(
                    date=today + timedelta(days=i),
                    question=q,
                    type=t,
                ))
            print(f"[database] Seeded {len(questions)} spark questions")

        # 违禁词库
        result = await session.execute(select(BannedWord).limit(1))
        if result.scalar_one_or_none() is None:
            banned = [
                "广告联系微信", "加我微信", "代开发票", "赌博", "色情",
                "毒品", "枪支", "弹药", "炸药", "政治敏感",
                "诈骗", "刷单", "传销", "裸聊",
            ]
            for w in banned:
                session.add(BannedWord(word=w, level="high"))
            print(f"[database] Seeded {len(banned)} banned words")

        await session.commit()


async def _migrate_sqlite_columns() -> None:
    """SQLite 轻量迁移：检测并补充新列。

    SQLAlchemy create_all 只对不存在的表生效，已存在的表不会 ALTER。
    这里手动检查 information_schema 并 ALTER TABLE ADD COLUMN。
    """
    migrations = [
        ("users", "llm_api_url", "VARCHAR(255) DEFAULT ''"),
        ("users", "llm_api_key", "VARCHAR(255) DEFAULT ''"),
        ("ideas", "publication_status", "VARCHAR(16) NOT NULL DEFAULT 'draft'"),
        ("ideas", "visibility", "VARCHAR(16) NOT NULL DEFAULT 'private'"),
        ("ideas", "license_code", "VARCHAR(32)"),
        ("ideas", "license_text_snapshot", "TEXT"),
        ("ideas", "license_version", "VARCHAR(32)"),
        ("ideas", "allow_fork", "BOOLEAN NOT NULL DEFAULT 0"),
        ("ideas", "published_at", "DATETIME"),
        ("ideas", "archived_at", "DATETIME"),
        ("ideas", "legacy_license_review_status", "VARCHAR(16) NOT NULL DEFAULT 'not_required'"),
        ("ideas", "legacy_license_review_notified_at", "DATETIME"),
        ("ideas", "legacy_license_reviewed_at", "DATETIME"),
        ("fork_relations", "metadata", "JSON"),
    ]
    async with engine.begin() as conn:
        for table, column, ddl in migrations:
            # 检查列是否存在
            res = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing_cols = {row[1] for row in res.fetchall()}
            if column not in existing_cols:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                print(f"[database] Migrated: {table}.{column} added")

        # One-time legacy backfill for existing SQLite databases. Fresh databases have no
        # rows at this point; newly-created Ideas after this marker keep draft/private defaults.
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS app_schema_migrations "
            "(version VARCHAR(120) PRIMARY KEY, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        ))
        applied = await conn.execute(text(
            "SELECT version FROM app_schema_migrations WHERE version = '001_idea_visibility_and_acl'"
        ))
        if applied.scalar_one_or_none() is None:
            await conn.execute(text("""
                UPDATE ideas
                SET publication_status = 'published',
                    visibility = 'public',
                    license_code = 'legacy_unspecified',
                    allow_fork = 0,
                    is_forkable = 0,
                    legacy_license_review_status = 'pending',
                    published_at = COALESCE(published_at, created_at)
                WHERE status = 'active'
            """))
            await conn.execute(text(
                "INSERT INTO app_schema_migrations(version) VALUES ('001_idea_visibility_and_acl')"
            ))
            print("[database] SQLite legacy Idea visibility backfill applied")


async def _ensure_today_spark_question() -> None:
    """PG 环境启动时确保当日「今日一点」题目存在。

    与定时任务（00:05）和路由层 AI 兜底形成三重保险：
    1. 定时任务：每日 00:05 预生成
    2. 启动钩子（本函数）：服务重启时补题
    3. 路由层：用户请求时实时生成

    采用非阻塞模式：生成失败仅打日志，不阻断启动。
    """
    from datetime import date as date_type
    from models import SparkQuestion
    from services.spark_ai_service import generate_and_persist

    today = date_type.today()
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(SparkQuestion).where(SparkQuestion.date == today)
            )
            if result.scalar_one_or_none() is not None:
                return  # 已存在，跳过

            print(f"[database] no spark question for {today}, generating on startup...")
            q = await generate_and_persist(session, today)
            if q is not None:
                print(f"[database] startup spark question: type={q.type} q={q.question[:40]}")
            else:
                print(f"[database] startup spark question generation returned None")
    except Exception as e:
        # 启动钩子失败不阻断服务，路由层还有兜底
        print(f"[database] startup spark question failed (non-blocking): {e}")


async def close_engine() -> None:
    await engine.dispose()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖注入：数据库 session。"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    """业务层使用的上下文管理器。"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
