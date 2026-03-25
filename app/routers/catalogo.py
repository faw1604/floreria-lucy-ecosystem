from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.productos import Producto

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def catalogo_html():
    try:
        with open("app/catalogo.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="catalogo.html no encontrado")

@router.get("/historia", response_class=HTMLResponse)
async def historia_html():
    try:
        with open("app/pages/historia.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

@router.get("/contacto", response_class=HTMLResponse)
async def contacto_html():
    try:
        with open("app/pages/contacto.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

@router.get("/facturacion", response_class=HTMLResponse)
async def facturacion_html():
    try:
        with open("app/pages/facturacion.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

@router.get("/legal", response_class=HTMLResponse)
async def legal_html():
    try:
        with open("app/pages/legal.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

@router.get("/productos")
async def catalogo_productos(
    categoria: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Producto)
        .where(
            Producto.activo == True,
            Producto.disponible_hoy == True,
            Producto.imagen_url.isnot(None),
        )
        .order_by(Producto.categoria, Producto.nombre)
    )
    if categoria:
        query = query.where(Producto.categoria == categoria)
    result = await db.execute(query)
    productos = result.scalars().all()
    return [
        {
            "id": p.id,
            "codigo": p.codigo,
            "nombre": p.nombre,
            "categoria": p.categoria,
            "precio": p.precio,
            "precio_descuento": p.precio_descuento,
            "precio_display": f"${p.precio // 100:,}",
            "precio_descuento_display": f"${p.precio_descuento // 100:,}" if p.precio_descuento else None,
            "descripcion": p.descripcion,
            "imagen_url": p.imagen_url,
            "disponible_hoy": p.disponible_hoy,
            "etiquetas": p.etiquetas,
            "dimensiones": p.dimensiones,
        }
        for p in productos
    ]
