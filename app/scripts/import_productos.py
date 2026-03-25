import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import async_session, inicializar_db
from app.models.productos import Producto
from sqlalchemy import select

# Ruta al archivo exportado de Kyte
ARCHIVO = os.environ.get(
    "PRODUCTOS_FILE",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "Products.csv"),
)


def leer_productos_xlsx(path: str) -> list[dict]:
    """Lee productos desde XLSX de Kyte."""
    import openpyxl
    from openpyxl.worksheet.datavalidation import DataValidation
    _orig_init = DataValidation.__init__
    def _patched_init(self, *args, **kwargs):
        try:
            _orig_init(self, *args, **kwargs)
        except ValueError:
            kwargs.pop("errorStyle", None)
            _orig_init(self, *args, errorStyle="stop", **kwargs)
    DataValidation.__init__ = _patched_init
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    productos = []
    headers = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = row
            continue
        data = dict(zip(headers, row))
        nombre = data.get("Nombre*") or data.get("Nombre")
        if not nombre:
            continue
        codigo = data.get("Código") or data.get("C\u00f3digo") or ""
        categoria = data.get("Categoría") or data.get("Categor\u00eda") or "Sin categoría"
        descripcion = data.get("Descripción") or data.get("Descripci\u00f3n") or ""

        # Precio y costo — vienen como enteros (950 = $950) o strings con separadores
        precio_raw = data.get("Precio*") or data.get("Precio") or 0
        costo_raw = data.get("Costo unitario") or data.get("Costo") or 0

        precio = limpiar_precio(precio_raw)
        costo = limpiar_precio(costo_raw)

        productos.append({
            "codigo": str(codigo).strip() if codigo else None,
            "nombre": str(nombre).strip(),
            "categoria": str(categoria).strip(),
            "precio": precio,
            "costo": costo,
            "descripcion": str(descripcion).strip() if descripcion else None,
        })
    wb.close()
    return productos


def leer_productos_csv(path: str) -> list[dict]:
    """Lee productos desde CSV de Kyte."""
    import csv
    productos = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nombre = row.get("Nombre*") or row.get("Nombre") or ""
            if not nombre.strip():
                continue
            codigo = row.get("Código") or row.get("Codigo") or ""
            categoria = row.get("Categoría") or row.get("Categoria") or "Sin categoría"
            descripcion = row.get("Descripción") or row.get("Descripcion") or ""
            precio_raw = row.get("Precio*") or row.get("Precio") or "0"
            costo_raw = row.get("Costo unitario") or row.get("Costo") or "0"

            precio = limpiar_precio(precio_raw)
            costo = limpiar_precio(costo_raw)

            productos.append({
                "codigo": codigo.strip() if codigo.strip() else None,
                "nombre": nombre.strip(),
                "categoria": categoria.strip(),
                "precio": precio,
                "costo": costo,
                "descripcion": descripcion.strip() if descripcion.strip() else None,
            })
    return productos


def limpiar_precio(valor) -> int:
    """Convierte precio a centavos. Maneja: 950, '1.000', '1,500', '950.00'."""
    if valor is None:
        return 0
    if isinstance(valor, (int, float)):
        return int(valor * 100)
    s = str(valor).strip().replace("$", "").replace(",", "").strip()
    if not s:
        return 0
    # "1.000" con punto como separador de miles (sin decimales reales del CSV de Kyte)
    # Si tiene exactamente un punto y 3 dígitos después, es separador de miles
    if "." in s:
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            # Separador de miles: 1.000 = 1000
            s = s.replace(".", "")
        elif len(parts) == 2 and len(parts[1]) <= 2:
            # Decimal: 950.50 = 950.50
            return int(float(s) * 100)
    try:
        return int(float(s) * 100)
    except ValueError:
        return 0


async def importar(path: str):
    await inicializar_db()

    if path.endswith(".xlsx"):
        productos = leer_productos_xlsx(path)
    else:
        productos = leer_productos_csv(path)

    print(f"Leidos {len(productos)} productos del archivo")

    insertados = 0
    saltados = 0

    async with async_session() as session:
        for p in productos:
            # Skip si ya existe por código
            if p["codigo"]:
                result = await session.execute(
                    select(Producto).where(Producto.codigo == p["codigo"])
                )
                if result.scalar_one_or_none():
                    saltados += 1
                    continue

            session.add(Producto(
                codigo=p["codigo"],
                nombre=p["nombre"],
                categoria=p["categoria"],
                precio=p["precio"],
                costo=p["costo"],
                descripcion=p["descripcion"],
                activo=True,
                disponible_hoy=True,
            ))
            insertados += 1

        await session.commit()

    print(f"Insertados: {insertados}")
    print(f"Saltados (ya existian): {saltados}")
    print("Importacion de productos completada")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else ARCHIVO
    asyncio.run(importar(path))
