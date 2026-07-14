"""数据库初始化诊断脚本 — 不依赖 Tee-Object"""
import sys, os, asyncio, io, contextlib

os.chdir(r"f:\treaFiles\Ideas\ideas\idea-app\backend")
sys.path.insert(0, r"f:\treaFiles\Ideas\ideas\idea-app\backend")

LOG_PATH = r"f:\treaFiles\Ideas\ideas\_db_test.txt"
log = open(LOG_PATH, "w", encoding="utf-8")

# 把 stdout/stderr 重定向到 log 文件，捕获所有 print
class _Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
            except Exception:
                pass
    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass

sys.stdout = _Tee(log)
sys.stderr = _Tee(log)


async def main():
    log.write("=== init_engine test ===\n"); log.flush()
    try:
        import database
        log.write(f"before init: dialect={database.DB_DIALECT}, url={database.DATABASE_URL}\n"); log.flush()
        await database.init_engine()
        log.write(f"after init: dialect={database.DB_DIALECT}, url={database.DATABASE_URL}\n"); log.flush()
        # 测试查询
        from sqlalchemy import text
        async with database.async_session_factory() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM ideas"))
            count = result.scalar()
            log.write(f"ideas count: {count}\n"); log.flush()
            result = await session.execute(text("SELECT COUNT(*) FROM spark_questions"))
            count = result.scalar()
            log.write(f"spark_questions count: {count}\n"); log.flush()
            result = await session.execute(text("SELECT COUNT(*) FROM banned_words"))
            count = result.scalar()
            log.write(f"banned_words count: {count}\n"); log.flush()
        log.write("\n=== DB INIT OK ===\n")
    except Exception as e:
        import traceback
        log.write(f"ERROR: {type(e).__name__}: {e}\n")
        log.write(traceback.format_exc())
    log.close()


asyncio.run(main())
