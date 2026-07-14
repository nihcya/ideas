import sys, os
os.chdir(r"f:\treaFiles\Ideas\ideas\idea-app\backend")
sys.path.insert(0, r"f:\treaFiles\Ideas\ideas\idea-app\backend")
log = open(r"f:\treaFiles\Ideas\ideas\_backend_test.txt", "w", encoding="utf-8")
log.write("=== Backend import test ===\n"); log.flush()
try:
    from config import settings
    log.write(f"config ok: env={settings.app_env}, deepseek_mock={not settings.is_deepseek_configured}\n"); log.flush()
    from database import init_engine, DB_DIALECT, DATABASE_URL
    log.write(f"database ok: dialect={DB_DIALECT}\n"); log.flush()
    from models import User, Idea, VaultItem, ForkRelation, SparkQuestion, SparkDraft, SparkSubmission, Notification, AuditLog, BannedWord
    log.write("models ok\n"); log.flush()
    from schemas import auth, idea, vault, spark, user, notification, settings as settings_schema, common
    log.write("schemas ok\n"); log.flush()
    from services.color_pool import random_color, COLOR_POOL
    log.write(f"color_pool ok: {len(COLOR_POOL)} colors\n"); log.flush()
    from services.deepseek_client import call_collide_ai, call_evolve_ai, call_audit_ai, SAMPER_ANGLES
    log.write("deepseek_client ok\n"); log.flush()
    from services.jwt_service import create_access_token, decode_token
    log.write("jwt_service ok\n"); log.flush()
    from services.cache import cache
    log.write("cache ok\n"); log.flush()
    from services.audit_service import audit_content, write_audit_log
    log.write("audit_service ok\n"); log.flush()
    from services.fade_service import check_and_fade
    log.write("fade_service ok\n"); log.flush()
    from services.spark_service import get_today_question, get_or_create_draft, has_submitted
    log.write("spark_service ok\n"); log.flush()
    from deps import get_db, get_current_user, get_optional_user
    log.write("deps ok\n"); log.flush()
    from routers import get_all_routers
    routers = get_all_routers()
    log.write(f"routers ok: {len(routers)} routers\n"); log.flush()
    for r in routers:
        log.write(f"  - {r.prefix} ({len(r.routes)} routes)\n")
    log.flush()
    from main import app
    log.write(f"main app ok: {len(app.routes)} total routes\n"); log.flush()
    log.write("\n=== ALL OK ===\n")
except SystemExit as e:
    log.write(f"SystemExit: {e}\n")
except Exception as e:
    import traceback
    log.write(f"ERROR: {type(e).__name__}: {e}\n")
    log.write(traceback.format_exc())
log.close()
