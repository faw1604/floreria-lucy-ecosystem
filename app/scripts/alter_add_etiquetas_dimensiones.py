"""Add etiquetas and dimensiones columns to productos table."""
import asyncio, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv()

async def main():
    from app.database import engine
    from sqlalchemy import text
    async with engine.begin() as conn:
        for col in ['etiquetas', 'dimensiones']:
            result = await conn.execute(text(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='productos' AND column_name='{col}'"
            ))
            if result.fetchone():
                print(f"Column {col} already exists.")
            else:
                await conn.execute(text(f"ALTER TABLE productos ADD COLUMN {col} TEXT"))
                print(f"Column {col} added.")

if __name__ == "__main__":
    asyncio.run(main())
