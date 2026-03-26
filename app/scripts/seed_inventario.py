"""Seed de insumos florales y no florales para Florería Lucy."""
import asyncio
from sqlalchemy import select
from app.database import engine, async_session
from app.models.inventario import InsumoFloral, InsumoNoFloral, InsumoProducto

# Ensure tables exist
from app.database import Base

PRINCIPALES = [
    ("Rosas", "Roja"), ("Rosas", "Blanca"), ("Rosas", "Color"),
    ("Gerberas", "Rosa"), ("Gerberas", "Mixtas"),
    ("Girasol", None),
    ("Lirios", "Blanco"), ("Lirios", "Rosa"),
    ("Tulipanes", "Rojo"), ("Tulipanes", "Blanco"), ("Tulipanes", "Morado"), ("Tulipanes", "Rosa"), ("Tulipanes", "Naranja"),
    ("Margaritas", "Blanca"), ("Margaritas", "Color"),
    ("Astromelia", "Blanca"), ("Astromelia", "Color"),
    ("Clavel", None),
    ("Polar", None),
    ("Gladiola/Perritos", None),
]

OTRAS_FLORES = [
    "Agapando", "Alhelí", "Alium", "Alcatraz", "Anémona", "Aquilea", "Artemisa",
    "Aster", "Aster Matsumoto", "Ave del Paraíso", "Baby", "Calla Lilas",
    "Cempasúchil", "Clavelina", "Col de Ornato", "Craspedia", "Delphinium",
    "Encaje", "Hawaiian", "Hipéricum", "Hortensia", "Liatriz", "Limonium/Caspia",
    "Lisianthus", "Mini Gerbera", "Mini Rosa", "Orquídea", "Ping Pong/Scabiosa",
    "Protea", "Ranunculus", "Rosa Inglesa", "Roxana/Flamingo", "Spider", "Statice",
    "Tulipán", "Wax Flower",
]

FOLLAJES = [
    "Amaranto", "Camedor", "Cambray", "Campana Irlandesa", "Camelia",
    "Clavo Japonés", "Clavo Nacional", "Cola de Zorra", "Cola de Zorro",
    "Curly Widow", "Dollar", "Dracenia", "Dusty Miller", "Espuma Morada",
    "Fornio", "Green Treek", "Gummi", "Hiedra", "Hoja de Ave", "Leather",
    "Listón", "Maicera", "Mini Dollar", "Piñanona", "Ruscus", "Safari",
    "Solidago", "Tulia/Pino",
]

NO_FLORALES = [
    ("Oasis", None),
    ("Mecánicas de Oasis", None),
    ("Cajas", "Mini"), ("Cajas", "Chica"), ("Cajas", "Mediana"), ("Cajas", "Grande"),
    ("Cajas", "Rectangular"), ("Cajas", "Corazón Chico"), ("Cajas", "Corazón Grande"),
    ("Cajas", "Cilindro Chico"), ("Cajas", "Cilindro Grande"),
    ("Canastas", "Chica"), ("Canastas", "Mediana"), ("Canastas", "Grande"),
    ("Jarrones", "Cilindro"), ("Jarrones", "Bombacho"), ("Jarrones", "Otro"),
    ("Violeteros", None),
    ("Papel Coreano", "Blanco"), ("Papel Coreano", "Negro"), ("Papel Coreano", "Guinda"),
    ("Papel Coreano", "Rosa"), ("Papel Coreano", "Morado"), ("Papel Coreano", "Otro Color"),
    ("Listones", None),
    ("Otro", "Especificar"),
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(select(InsumoFloral).limit(1))
        if result.scalar_one_or_none():
            print("Insumos florales ya existen, saltando seed floral.")
        else:
            # Principales
            for familia, variante in PRINCIPALES:
                db.add(InsumoFloral(familia=familia, variante=variante, categoria="principal", descuento_automatico=True))
            # Otras flores
            for nombre in OTRAS_FLORES:
                db.add(InsumoFloral(familia=nombre, variante=None, categoria="otras_flores", descuento_automatico=False))
            # Follajes
            for nombre in FOLLAJES:
                db.add(InsumoFloral(familia=nombre, variante=None, categoria="follajes", descuento_automatico=False))
            await db.commit()
            print(f"Sembrados {len(PRINCIPALES) + len(OTRAS_FLORES) + len(FOLLAJES)} insumos florales.")

        # No florales
        result2 = await db.execute(select(InsumoNoFloral).limit(1))
        if result2.scalar_one_or_none():
            print("Insumos no florales ya existen, saltando seed no floral.")
        else:
            for cat, var in NO_FLORALES:
                db.add(InsumoNoFloral(categoria=cat, variante=var))
            await db.commit()
            print(f"Sembrados {len(NO_FLORALES)} insumos no florales.")

    print("Seed de inventario completado.")


if __name__ == "__main__":
    asyncio.run(seed())
