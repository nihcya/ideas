"""Run daily from cron/systemd to enforce the 90-day legacy license window."""
import asyncio

from database import async_session_factory, engine
from services.legacy_license_transition import process_legacy_license_deadlines


async def main() -> None:
    try:
        async with async_session_factory() as db:
            result = await process_legacy_license_deadlines(db)
            print(
                "legacy_license_transition "
                f"reminders_sent={result['reminders_sent']} "
                f"expired={result['expired']}"
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
