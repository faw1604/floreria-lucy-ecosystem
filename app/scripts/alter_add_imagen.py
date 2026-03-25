import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from app.database import async_session, inicializar_db

async def migrate():
    await inicializar_db()
    async with async_session() as session:
        await session.execute(text("ALTER TABLE productos ADD COLUMN IF NOT EXISTS imagen_url TEXT"))
        await session.commit()
        print("Column imagen_url added successfully")

if __name__ == "__main__":
    asyncio.run(migrate())
