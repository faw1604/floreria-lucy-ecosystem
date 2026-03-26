"""Seed de insumos florales y no florales para Florería Lucy.
Re-siembra limpia: borra datos existentes y vuelve a insertar."""
import asyncio
from sqlalchemy import select, delete
from app.database import engine, async_session, Base
from app.models.inventario import InsumoFloral, InsumoNoFloral

# Flores principales: familia + variantes (colores) con cantidad y estado individual
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

# Otras flores: solo nombre + estado (sin cantidad)
OTRAS_FLORES = [
    "Agapando", "Alhelí", "Alium", "Alcatraz", "Anémona", "Aquilea", "Artemisa",
    "Aster", "Aster Matsumoto", "Ave del Paraíso", "Baby", "Calla Lilas",
    "Cempasúchil", "Clavelina", "Col de Ornato", "Craspedia", "Delphinium",
    "Encaje", "Hawaiian", "Hipéricum", "Hortensia", "Liatriz", "Limonium/Caspia",
    "Lisianthus", "Mini Gerbera", "Mini Rosa", "Orquídea", "Ping Pong/Scabiosa",
    "Protea", "Ranunculus", "Rosa Inglesa", "Roxana/Flamingo", "Spider", "Statice",
    "Tulipán", "Wax Flower",
]

# Follajes: solo nombre + estado (sin cantidad)
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
        # Limpiar tablas
        await db.execute(delete(InsumoFloral))
        await db.execute(delete(InsumoNoFloral))
        await db.commit()
        print("Tablas limpiadas.")

        # Principales — con cantidad y descuento automatico
        for familia, variante in PRINCIPALES:
            db.add(InsumoFloral(familia=familia, variante=variante, categoria="principal", descuento_automatico=True, cantidad=0, stock_estado="en_stock"))

        # Otras flores — sin cantidad (siempre 0), solo estado
        for nombre in OTRAS_FLORES:
            db.add(InsumoFloral(familia=nombre, variante=None, categoria="otras_flores", descuento_automatico=False, cantidad=0, stock_estado="en_stock"))

        # Follajes — sin cantidad (siempre 0), solo estado
        for nombre in FOLLAJES:
            db.add(InsumoFloral(familia=nombre, variante=None, categoria="follajes", descuento_automatico=False, cantidad=0, stock_estado="en_stock"))

        # No florales
        for cat, var in NO_FLORALES:
            db.add(InsumoNoFloral(categoria=cat, variante=var, cantidad=0, stock_estado="en_stock"))

        await db.commit()
        total_floral = len(PRINCIPALES) + len(OTRAS_FLORES) + len(FOLLAJES)
        print(f"Sembrados {total_floral} insumos florales ({len(PRINCIPALES)} principales, {len(OTRAS_FLORES)} otras flores, {len(FOLLAJES)} follajes).")
        print(f"Sembrados {len(NO_FLORALES)} insumos no florales.")
        print("Seed de inventario completado.")


if __name__ == "__main__":
    asyncio.run(seed())
