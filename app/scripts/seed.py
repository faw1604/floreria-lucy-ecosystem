import asyncio
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import async_session, inicializar_db
from app.models.funerarias import Funeraria
from app.models.pagos import MetodoPago
from app.models.flores import TipoFlor
from sqlalchemy import select

FUNERARIAS = [
    {"nombre": "Mausoleos Luz Eterna", "aliases": ["Mausoleos", "Luz Eterna"], "direccion": "Av. Hacienda de la Cantera 2603, Cumbres II", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Latinoamericana Recinto Funeral", "aliases": ["Latinoamericana", "Recinto Funeral"], "direccion": "Av. Universidad 2501 esq. Ramírez Calderón, San Felipe", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funerales Miranda Tecnológico", "aliases": ["Miranda Tec", "Miranda Tecnológico"], "direccion": "Av. Tecnológico 7713, Lourdes", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funerales Miranda Pacheco", "aliases": ["Miranda Pacheco"], "direccion": "Av. Carlos Pacheco Villa 1207, Cerro Cnel. I", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funeraria San Felipe", "aliases": ["San Felipe"], "direccion": "Av. División del Norte 2102, Altavista", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funeraria La Colina", "aliases": ["La Colina", "Panteón La Colina"], "direccion": "Calle 16 de Septiembre 1401, Tierra y Libertad", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Capillas Todas las Almas", "aliases": ["Todas las Almas", "Ángeles"], "direccion": "Av. Zaragoza 706, Col. Las Granjas", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funeraria Vida Plena", "aliases": ["Vida Plena"], "direccion": "Calle Riva Palacio esq. C. 25, Santo Niño", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "La Cineraria", "aliases": ["La Cineraria", "Cineraria"], "direccion": "Av. Francisco Zarco 6608, Campesina Nueva", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funeraria Elian Perches", "aliases": ["Perches"], "direccion": "Av. Tecnológico 10309, Deportistas", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funerales Hernández", "aliases": ["Hernández", "Hernández Centro"], "direccion": "Av. Benito Juárez 1701, Zona Centro", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funeraria Némesis", "aliases": ["Némesis"], "direccion": "Av. Benito Juárez 4700, Cerro Cnel. I", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Funerales Miranda Villa Juárez", "aliases": ["Miranda Villa Juárez"], "direccion": "C. 15a 1701, Villa Juárez", "zona": "Azul", "costo_envio": 15900},
    {"nombre": "Nuevo Amanecer", "aliases": ["Nuevo Amanecer"], "direccion": "Referencia: enfrente de Miranda Pacheco", "zona": "Morada", "costo_envio": 9900},
    {"nombre": "Cineraria Tecnológico", "aliases": ["Cineraria Tec"], "direccion": "Referencia: 3 min de Miranda Tecnológico", "zona": "Morada", "costo_envio": 9900},
]

METODOS_PAGO = [
    {"tipo": "transferencia", "banco": "BanCoppel", "titular": "Fernando Abaroa Willis", "clabe": "", "activo": False, "solo_sucursal": False},
    {"tipo": "transferencia", "banco": "BBVA", "titular": "Fernando Abaroa Willis", "clabe": "", "activo": True, "solo_sucursal": False},
    {"tipo": "transferencia", "banco": "Banco Azteca", "titular": "Fernando Abaroa Willis", "clabe": "", "activo": False, "solo_sucursal": False},
    {"tipo": "oxxo", "banco": None, "titular": "Fernando Abaroa Willis", "numero_tarjeta": "4217470047518572", "activo": True, "solo_sucursal": False},
    {"tipo": "tarjeta_fisica", "banco": None, "titular": None, "activo": True, "solo_sucursal": True},
]

FLORES_BASE = [
    "Rosa roja", "Rosa blanca", "Rosa rosa", "Rosa amarilla", "Rosa naranja",
    "Girasol", "Lili blanco", "Lili rosado", "Gerbera", "Margarita",
    "Clavel", "Alstroemeria", "Hortensia", "Tulipán", "Orquídea",
]

async def seed():
    await inicializar_db()
    async with async_session() as session:
        # Funerarias
        result = await session.execute(select(Funeraria))
        if not result.scalars().first():
            for f in FUNERARIAS:
                session.add(Funeraria(
                    nombre=f["nombre"],
                    aliases=json.dumps(f["aliases"], ensure_ascii=False),
                    direccion=f["direccion"],
                    zona=f["zona"],
                    costo_envio=f["costo_envio"],
                ))
            await session.commit()
            print(f"✅ {len(FUNERARIAS)} funerarias insertadas")
        else:
            print("⏭️  Funerarias ya existen — omitiendo")

        # Métodos de pago
        result = await session.execute(select(MetodoPago))
        if not result.scalars().first():
            for m in METODOS_PAGO:
                session.add(MetodoPago(**m))
            await session.commit()
            print(f"✅ {len(METODOS_PAGO)} métodos de pago insertados")
        else:
            print("⏭️  Métodos de pago ya existen — omitiendo")

        # Flores base
        result = await session.execute(select(TipoFlor))
        if not result.scalars().first():
            for nombre in FLORES_BASE:
                session.add(TipoFlor(nombre=nombre, disponible_hoy=True))
            await session.commit()
            print(f"✅ {len(FLORES_BASE)} flores insertadas")
        else:
            print("⏭️  Flores ya existen — omitiendo")

    print("✅ Seed completado")

if __name__ == "__main__":
    asyncio.run(seed())
