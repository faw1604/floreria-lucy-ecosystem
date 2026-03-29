"""
Migración para el rediseño KDS del taller.
Agrega columnas nuevas a pedidos y seeds de configuracion_negocio.

Ejecutar: python -m app.scripts.migrate_taller_kds
"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def migrate():
    async with engine.begin() as conn:
        # ── Nuevas columnas en pedidos ──
        cols = {
            "metodo_entrega": "VARCHAR(30)",
            "modo_fecha_fuerte_lote": "VARCHAR(100)",
            "listo_at": "TIMESTAMP",
            "produccion_at": "TIMESTAMP",
            "cancelado_razon": "TEXT",
        }
        for col, tipo in cols.items():
            try:
                await conn.execute(text(f"ALTER TABLE pedidos ADD COLUMN {col} {tipo}"))
                print(f"  ✓ pedidos.{col} agregado")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"  – pedidos.{col} ya existe")
                else:
                    print(f"  ✗ pedidos.{col}: {e}")

        # ── Seeds de configuracion_negocio para fecha fuerte ──
        seeds = [
            ("modo_fecha_fuerte", "false", "Activa el modo fecha fuerte (producción por lotes)"),
            ("fecha_fuerte_fecha", "", "Fecha del evento de fecha fuerte (YYYY-MM-DD)"),
            ("fecha_fuerte_dias_antes", "2", "Días antes de la fecha fuerte para activar"),
            ("fecha_fuerte_acepta_funerales", "true", "Acepta pedidos de funeral en fecha fuerte"),
        ]
        for clave, valor, desc in seeds:
            try:
                await conn.execute(text(
                    "INSERT INTO configuracion_negocio (clave, valor, descripcion) "
                    "VALUES (:c, :v, :d) ON CONFLICT (clave) DO NOTHING"
                ), {"c": clave, "v": valor, "d": desc})
                print(f"  ✓ config: {clave}")
            except Exception as e:
                print(f"  – config {clave}: {e}")

        # ── Backfill metodo_entrega en pedidos existentes ──
        await conn.execute(text("""
            UPDATE pedidos SET metodo_entrega = 'mostrador'
            WHERE metodo_entrega IS NULL
              AND direccion_entrega IS NULL AND zona_entrega IS NULL
              AND (tipo_especial IS NULL OR tipo_especial NOT IN ('Funeral', 'Recoger'))
              AND canal = 'Mostrador'
        """))
        await conn.execute(text("""
            UPDATE pedidos SET metodo_entrega = 'recoger'
            WHERE metodo_entrega IS NULL
              AND direccion_entrega IS NULL AND zona_entrega IS NULL
              AND tipo_especial = 'Recoger'
        """))
        await conn.execute(text("""
            UPDATE pedidos SET metodo_entrega = 'funeral_envio'
            WHERE metodo_entrega IS NULL
              AND tipo_especial = 'Funeral' AND direccion_entrega IS NOT NULL
        """))
        await conn.execute(text("""
            UPDATE pedidos SET metodo_entrega = 'funeral_recoger'
            WHERE metodo_entrega IS NULL
              AND tipo_especial = 'Funeral' AND direccion_entrega IS NULL
        """))
        await conn.execute(text("""
            UPDATE pedidos SET metodo_entrega = 'envio'
            WHERE metodo_entrega IS NULL
              AND direccion_entrega IS NOT NULL
        """))
        await conn.execute(text("""
            UPDATE pedidos SET metodo_entrega = 'recoger'
            WHERE metodo_entrega IS NULL
              AND direccion_entrega IS NULL AND zona_entrega IS NULL
        """))
        print("  ✓ Backfill metodo_entrega completado")

    print("\n✅ Migración KDS completada")


if __name__ == "__main__":
    asyncio.run(migrate())
