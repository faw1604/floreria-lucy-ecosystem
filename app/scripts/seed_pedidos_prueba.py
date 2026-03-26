"""Insertar 3 pedidos de prueba en Railway: general, funeral, recoger en tienda."""
import asyncio
from app.database import engine, async_session, Base
from app.models.pedidos import Pedido
from sqlalchemy import select, delete
from datetime import datetime
import zoneinfo

TZ = zoneinfo.ZoneInfo("America/Chihuahua")

PEDIDOS = [
    {
        "numero": "FL-2026-T001",
        "canal": "WhatsApp",
        "estado": "Nuevo",
        "horario_entrega": "tarde",
        "zona_entrega": "Morada",
        "direccion_entrega": "C. Sabino 610, Las Granjas, Chihuahua",
        "receptor_nombre": "Ana Garcia",
        "receptor_telefono": "6141112222",
        "dedicatoria": "Feliz cumpleanos mi amor",
        "notas_internas": "Casa color azul, tocar el timbre dos veces",
        "forma_pago": "Transferencia",
        "pago_confirmado": True,
        "subtotal": 68000,
        "envio": 9900,
        "total": 77900,
        "tipo_especial": None,
    },
    {
        "numero": "FL-2026-T002",
        "canal": "WhatsApp",
        "estado": "Nuevo",
        "horario_entrega": "manana",
        "hora_exacta": "11:00am",
        "zona_entrega": "Azul",
        "direccion_entrega": "Funeraria San Jose, Sala 3, Av. Juarez 450",
        "receptor_nombre": "Familia Martinez",
        "receptor_telefono": "6143334444",
        "dedicatoria": None,
        "notas_internas": "Funeraria San Jose, Sala 3. Velacion a las 12pm. Banda: Descanse en paz Don Roberto",
        "forma_pago": "Efectivo",
        "pago_confirmado": False,
        "subtotal": 120000,
        "envio": 15900,
        "total": 135900,
        "tipo_especial": "Funeral",
    },
    {
        "numero": "FL-2026-T003",
        "canal": "Web",
        "estado": "Nuevo",
        "horario_entrega": None,
        "hora_exacta": "4:00pm",
        "zona_entrega": None,
        "direccion_entrega": None,
        "receptor_nombre": "Juan Perez",
        "receptor_telefono": "6145556666",
        "dedicatoria": "Para mi mama con todo mi carino",
        "notas_internas": None,
        "forma_pago": "Efectivo en tienda",
        "pago_confirmado": False,
        "subtotal": 45000,
        "envio": 0,
        "total": 45000,
        "tipo_especial": None,
    },
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        hoy = datetime.now(TZ).date()

        for data in PEDIDOS:
            # Delete if exists
            result = await db.execute(select(Pedido).where(Pedido.numero == data["numero"]))
            existing = result.scalar_one_or_none()
            if existing:
                await db.delete(existing)
                await db.flush()
                print(f"  Eliminado pedido existente {data['numero']}")

            pedido = Pedido(
                numero=data["numero"],
                canal=data["canal"],
                estado=data["estado"],
                fecha_entrega=hoy,
                horario_entrega=data["horario_entrega"],
                hora_exacta=data.get("hora_exacta"),
                zona_entrega=data["zona_entrega"],
                direccion_entrega=data["direccion_entrega"],
                receptor_nombre=data["receptor_nombre"],
                receptor_telefono=data["receptor_telefono"],
                dedicatoria=data["dedicatoria"],
                notas_internas=data["notas_internas"],
                forma_pago=data["forma_pago"],
                pago_confirmado=data["pago_confirmado"],
                subtotal=data["subtotal"],
                envio=data["envio"],
                total=data["total"],
                tipo_especial=data["tipo_especial"],
                estado_florista="pendiente_aprobacion",
            )
            db.add(pedido)

        await db.commit()
        print(f"Insertados 3 pedidos de prueba para {hoy}:")
        print("  FL-2026-T001 — General (tarde, zona Morada, pago confirmado)")
        print("  FL-2026-T002 — Funeral (manana, zona Azul, pago pendiente)")
        print("  FL-2026-T003 — Recoger en tienda (sin zona, pago pendiente)")


if __name__ == "__main__":
    asyncio.run(seed())
