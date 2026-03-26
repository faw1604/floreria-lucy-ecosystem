"""Add new fields to clientes table for registration, referrals, discounts."""
import asyncio, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv()

async def main():
    from app.database import engine
    from sqlalchemy import text
    columns = {
        'fecha_nacimiento': 'DATE',
        'fecha_aniversario': 'DATE',
        'descuento_primera_compra': 'BOOLEAN DEFAULT TRUE',
        'codigo_referido': 'VARCHAR(20)',
        'referido_por': 'VARCHAR(20)',
        'descuento_referido': 'INTEGER DEFAULT 0',
        'registrado_web': 'BOOLEAN DEFAULT FALSE',
    }
    async with engine.begin() as conn:
        for col, col_type in columns.items():
            result = await conn.execute(text(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='clientes' AND column_name='{col}'"
            ))
            if result.fetchone():
                print(f"  {col} already exists")
            else:
                await conn.execute(text(f"ALTER TABLE clientes ADD COLUMN {col} {col_type}"))
                print(f"  {col} added")

if __name__ == "__main__":
    asyncio.run(main())
