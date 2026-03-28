"""
Migración: Agregar campos para flujo WhatsApp en tabla pedidos
y crear tabla configuracion_negocio.
Ejecutar: python scripts/migrate_whatsapp_flow.py
"""
import asyncio
import os

DATABASE_URL = os.getenv(
    "DATABASE_PUBLIC_URL",
    "[REDACTED]"
)

# Convertir a asyncpg format
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def migrate():
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # --- Campos nuevos en pedidos ---
        nuevos_campos = [
            ("comprobante_pago_url", "TEXT"),
            ("comprobante_pago_at", "TIMESTAMP"),
            ("pago_confirmado_at", "TIMESTAMP"),
            ("pago_confirmado_por", "VARCHAR(50)"),
            ("nota_validacion", "TEXT"),
            ("webhook_url", "TEXT"),
        ]
        for campo, tipo in nuevos_campos:
            try:
                await conn.execute(text(
                    f"ALTER TABLE pedidos ADD COLUMN {campo} {tipo}"
                ))
                print(f"  + pedidos.{campo} ({tipo})")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print(f"  = pedidos.{campo} ya existe")
                else:
                    print(f"  ! pedidos.{campo}: {e}")

        # --- Tabla configuracion_negocio ---
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS configuracion_negocio (
                id SERIAL PRIMARY KEY,
                clave VARCHAR(100) UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                descripcion TEXT
            )
        """))
        print("  + tabla configuracion_negocio creada/verificada")

        # --- Datos iniciales de configuración ---
        datos = [
            ("banco_nombre", "BBVA", "Nombre del banco para pagos"),
            ("banco_titular", "Fernando Abaroa", "Titular de la cuenta bancaria"),
            ("banco_cuenta", "[Fer completa esto]", "Numero de cuenta bancaria"),
            ("banco_clabe", "[Fer completa esto]", "CLABE interbancaria"),
            ("banco_concepto", "Pedido Floreria Lucy", "Concepto sugerido para transferencia"),
            ("negocio_nombre", "Floreria Lucy", "Nombre del negocio"),
            ("negocio_direccion", "C. Sabino 610, Las Granjas, Chihuahua", "Direccion fisica"),
            ("negocio_telefono", "6143349392", "Telefono principal"),
            ("negocio_email", "florerialucychihuahua@gmail.com", "Correo electronico"),
        ]
        for clave, valor, desc in datos:
            await conn.execute(text("""
                INSERT INTO configuracion_negocio (clave, valor, descripcion)
                VALUES (:clave, :valor, :desc)
                ON CONFLICT (clave) DO NOTHING
            """), {"clave": clave, "valor": valor, "desc": desc})
            print(f"  + config: {clave}")

    await engine.dispose()
    print("\nMigracion completada.")


if __name__ == "__main__":
    asyncio.run(migrate())
