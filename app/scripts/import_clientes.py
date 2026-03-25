import asyncio
import csv
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import async_session, inicializar_db
from app.models.clientes import Cliente
from sqlalchemy import select

ARCHIVO = os.environ.get(
    "CLIENTES_FILE",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "Customers.csv"),
)


def limpiar_telefono(tel: str) -> str:
    """Limpia teléfono: quita '52' del inicio si tiene más de 10 dígitos."""
    # Solo dígitos
    digitos = "".join(c for c in tel if c.isdigit())
    if not digitos:
        return ""
    # Quitar prefijo 52 si tiene más de 10 dígitos
    if len(digitos) > 10 and digitos.startswith("52"):
        digitos = digitos[2:]
    return digitos


async def importar(path: str):
    await inicializar_db()

    clientes = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nombre = row.get("name") or row.get("Nombre") or ""
            telefono_raw = row.get("number") or row.get("Teléfono") or row.get("Telefono") or ""
            direccion = row.get("Dirección") or row.get("Direccion") or row.get("address") or ""
            email = row.get("Correo") or row.get("email") or ""

            nombre = nombre.strip()
            telefono = limpiar_telefono(telefono_raw)

            if not nombre or not telefono:
                continue

            clientes.append({
                "nombre": nombre,
                "telefono": telefono,
                "direccion_default": direccion.strip() if direccion.strip() else None,
                "email": email.strip() if email.strip() else None,
                "fuente": "Kyte",
            })

    print(f"Leidos {len(clientes)} clientes del archivo")

    insertados = 0
    saltados = 0

    async with async_session() as session:
        for c in clientes:
            # Skip si el teléfono ya existe
            result = await session.execute(
                select(Cliente).where(Cliente.telefono == c["telefono"])
            )
            if result.scalar_one_or_none():
                saltados += 1
                continue

            session.add(Cliente(
                nombre=c["nombre"],
                telefono=c["telefono"],
                direccion_default=c["direccion_default"],
                email=c["email"],
                fuente=c["fuente"],
            ))
            insertados += 1

        await session.commit()

    print(f"Insertados: {insertados}")
    print(f"Saltados (ya existian): {saltados}")
    print("Importacion de clientes completada")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else ARCHIVO
    asyncio.run(importar(path))
