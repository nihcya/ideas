"""一次性迁移脚本：把数据库中明文 llm_api_key 加密

使用前必须设置环境变量 LLM_KEY_ENCRYPTION_KEY。
执行：python scripts/encrypt_existing_api_keys.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from database import async_session_factory
from models import User
from services.crypto_service import encrypt


async def main():
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.llm_api_key != ""))
        users = result.scalars().all()
        count = 0
        for user in users:
            # Fernet 密文以 gAAAA 开头，避免重复加密
            if user.llm_api_key and not user.llm_api_key.startswith("gAAAA"):
                user.llm_api_key = encrypt(user.llm_api_key)
                count += 1
        await db.commit()
        print(f"已加密 {count} 个用户的 API Key")


if __name__ == "__main__":
    asyncio.run(main())
