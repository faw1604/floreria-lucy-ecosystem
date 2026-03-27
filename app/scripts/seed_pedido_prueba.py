"""Insert a test order into the Railway DB."""
import asyncio, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv()

async def main():
    from app.database import async_session, inicializar_db
    from app.models.pedidos import Pedido
    from sqlalchemy import select
    from datetime import datetime
    import zoneinfo

    tz = zoneinfo.ZoneInfo("America/Chihuahua")
    hoy = datetime.now(tz).date()

    await inicializar_db()
    async with async_session() as session:
        # Check if already exists
        r = await session.execute(select(Pedido).where(Pedido.numero == "FL-2026-TEST"))
        if r.scalar_one_or_none():
            print("Pedido FL-2026-TEST ya existe. Eliminando para recrear...")
            await session.execute(select(Pedido).where(Pedido.numero == "FL-2026-TEST"))
            existing = (await session.execute(select(Pedido).where(Pedido.numero == "FL-2026-TEST"))).scalar_one()
            await session.delete(existing)
            await session.commit()

        pedido = Pedido(
            numero="FL-2026-TEST",
            canal="WhatsApp",
            estado="Nuevo",
            fecha_entrega=hoy,
            horario_entrega="tarde",
            zona_entrega="Morada",
            direccion_entrega="C. Sabino 610, Las Granjas, Chihuahua",
            receptor_nombre="Prueba Técnica",
            receptor_telefono="6141234567",
            dedicatoria="Este es un pedido de prueba para verificar el ticket",
            notas_internas="Verificar impresión del ticket térmico",
            forma_pago="transferencia",
            pago_confirmado=True,
            subtotal=68000,
            envio=9900,
            total=77900,
            tipo_especial=None,
        )
        session.add(pedido)
        await session.commit()
        await session.refresh(pedido)
        print(f"Pedido insertado: id={pedido.id}, numero={pedido.numero}, fecha_entrega={pedido.fecha_entrega}")

if __name__ == "__main__":
    asyncio.run(main())
