"""自然淡出服务 — 定时任务调用"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings


async def check_and_fade(db: AsyncSession) -> dict:
    """执行淡出检查：7天未触碰→fading，8天未触碰→移出仓库。"""
    now = datetime.now(timezone.utc)
    fading_threshold = now - timedelta(days=settings.fade_fading_days)
    faded_threshold = now - timedelta(days=settings.fade_faded_days)

    # 1. 更新 status='fading'：7天未触碰
    fade_result = await db.execute(
        text("""
            UPDATE ideas SET status = 'fading'
            WHERE id IN (
                SELECT i.id FROM vault_items vi
                JOIN ideas i ON i.id = vi.idea_id
                WHERE i.status = 'active'
                  AND vi.last_touch_at < :fading_threshold
            )
        """),
        {"fading_threshold": fading_threshold},
    )
    faded_count = fade_result.rowcount if hasattr(fade_result, "rowcount") else 0

    # 2. 移出仓库：8天未触碰
    remove_result = await db.execute(
        text("""
            DELETE FROM vault_items
            WHERE last_touch_at < :faded_threshold
        """),
        {"faded_threshold": faded_threshold},
    )
    removed_count = remove_result.rowcount if hasattr(remove_result, "rowcount") else 0

    # 3. 将已移出仓库的 fading 点子标记为 faded
    #    条件：status='fading' 且该点子已不在任何仓库中（vault_items 中无记录）
    mark_result = await db.execute(
        text("""
            UPDATE ideas SET status = 'faded'
            WHERE status = 'fading'
              AND id NOT IN (SELECT idea_id FROM vault_items)
        """),
    )
    marked_count = mark_result.rowcount if hasattr(mark_result, "rowcount") else 0

    # 4. 物理删除未被 fork 的 faded 点子
    delete_result = await db.execute(
        text("""
            DELETE FROM ideas
            WHERE status = 'faded'
              AND id NOT IN (
                  SELECT parent_id FROM fork_relations
                  UNION
                  SELECT child_id FROM fork_relations
              )
        """),
    )
    deleted_count = delete_result.rowcount if hasattr(delete_result, "rowcount") else 0

    await db.commit()
    return {
        "faded_to_fading": faded_count,
        "removed_from_vault": removed_count,
        "marked_as_faded": marked_count,
        "physically_deleted": deleted_count,
    }
