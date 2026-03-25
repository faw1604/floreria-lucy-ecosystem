"""
Add precio_descuento column to productos table.

Usage:
    python -m app.scripts.alter_add_precio_descuento
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()


async def main():
    from app.database import engine
    from sqlalchemy import text

    async with engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='productos' AND column_name='precio_descuento'"
        ))
        if result.fetchone():
            print("Column precio_descuento already exists.")
            return

        await conn.execute(text(
            "ALTER TABLE productos ADD COLUMN precio_descuento INTEGER"
        ))
        print("Column precio_descuento added successfully.")


if __name__ == "__main__":
    asyncio.run(main())
