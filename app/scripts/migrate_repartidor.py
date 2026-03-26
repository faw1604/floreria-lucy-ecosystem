"""
Migración: agregar campos de repartidor a tabla pedidos
Ejecutar UNA sola vez: python -m app.scripts.migrate_repartidor
"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def migrar():
    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE pedidos
            ADD COLUMN IF NOT EXISTS inicio_ruta_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS entregado_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS foto_entrega_url VARCHAR,
            ADD COLUMN IF NOT EXISTS intento_fallido_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS nota_no_entrega VARCHAR
        """))
    print("Migracion repartidor completada")


if __name__ == "__main__":
    asyncio.run(migrar())
