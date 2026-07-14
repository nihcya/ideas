import sys, os
log = open(r"f:\treaFiles\Ideas\ideas\_diag2.txt", "w", encoding="utf-8")
log.write("start\n"); log.flush()
try:
    import pydantic
    log.write(f"pydantic: {pydantic.VERSION}\n"); log.flush()
    import pydantic_core
    log.write(f"pydantic_core: {pydantic_core.__version__}\n"); log.flush()
    from pydantic import BaseModel
    log.write("BaseModel ok\n"); log.flush()
    import fastapi
    log.write(f"fastapi: {fastapi.__version__}\n"); log.flush()
    import sqlalchemy, asyncpg, redis, openai, jose, passlib, apscheduler, aiosqlite, bcrypt, httpx
    log.write("all imports ok\n"); log.flush()
    log.write("SUCCESS\n")
except SystemExit as e:
    log.write(f"SystemExit: {e}\n")
except Exception as e:
    import traceback
    log.write(f"ERROR: {type(e).__name__}: {e}\n")
    log.write(traceback.format_exc())
log.close()
