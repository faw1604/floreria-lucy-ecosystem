from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models.reservas import Reserva
from app.models.productos import Producto
from app.core.config import TZ
from app.routers.auth import verificar_sesion

logger = logging.getLogger("floreria")

router = APIRouter()

def _now():
    """Datetime actual en Chihuahua, sin timezone (naive) para asyncpg."""
    return datetime.now(TZ).replace(tzinfo=None)


def _auth(panel_session: str | None):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")


async def _serializar_reserva(r, db: AsyncSession) -> dict:
    nombre = r.nombre_custom
    imagen_url = None
    codigo = None
    if r.producto_id:
        prod_result = await db.execute(select(Producto).where(Producto.id == r.producto_id))
        prod = prod_result.scalar_one_or_none()
        if prod:
            nombre = nombre or prod.nombre
            imagen_url = prod.imagen_url
            codigo = prod.codigo
    return {
        "id": r.id,
        "producto_id": r.producto_id,
        "nombre": nombre or "Sin nombre",
        "nombre_custom": r.nombre_custom,
        "codigo": codigo,
        "precio": r.precio,
        "foto_url": r.foto_url,
        "imagen_url": imagen_url,
        "florista_usuario": r.florista_usuario,
        "estado": r.estado,
        "pedido_id": r.pedido_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "vendida_at": r.vendida_at.isoformat() if r.vendida_at else None,
        "descartada_at": r.descartada_at.isoformat() if r.descartada_at else None,
        "descarte_razon": r.descarte_razon,
    }


# ─── Crear reserva (desde taller) ───
@router.post("/crear")
async def crear_reserva(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()

    producto_id = data.get("producto_id")
    nombre_custom = (data.get("nombre_custom") or "").strip()
    precio = data.get("precio")
    foto_url = data.get("foto_url")
    florista = (data.get("florista_usuario") or "florista").strip()

    if not producto_id and not nombre_custom:
        raise HTTPException(status_code=400, detail="Selecciona un producto o escribe un nombre")

    # Si viene producto_id, obtener precio del catálogo si no se especificó
    if producto_id and not precio:
        prod_result = await db.execute(select(Producto).where(Producto.id == producto_id))
        prod = prod_result.scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=400, detail="Producto no encontrado")
        precio = prod.precio_descuento if (prod.precio_descuento and prod.precio_descuento < prod.precio) else prod.precio

    if not precio or precio <= 0:
        raise HTTPException(status_code=400, detail="Precio es obligatorio")

    reserva = Reserva(
        producto_id=producto_id,
        nombre_custom=nombre_custom or None,
        precio=precio,
        foto_url=foto_url,
        florista_usuario=florista,
        estado="disponible",
        created_at=_now(),
    )
    db.add(reserva)
    await db.commit()
    await db.refresh(reserva)

    return await _serializar_reserva(reserva, db)


# ─── Disponibles (para POS) ───
@router.get("/disponibles")
async def disponibles(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(
        select(Reserva)
        .where(Reserva.estado == "disponible")
        .order_by(Reserva.created_at.desc())
    )
    reservas = result.scalars().all()
    return [await _serializar_reserva(r, db) for r in reservas]


# ─── Vender (vincula a pedido) ───
@router.post("/{reserva_id}/vender")
async def vender_reserva(
    reserva_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    pedido_id = data.get("pedido_id")

    result = await db.execute(
        select(Reserva).where(Reserva.id == reserva_id, Reserva.estado == "disponible")
    )
    reserva = result.scalar_one_or_none()
    if not reserva:
        raise HTTPException(status_code=409, detail="Reserva no disponible (ya vendida o descartada)")

    reserva.estado = "vendida"
    reserva.pedido_id = pedido_id
    reserva.vendida_at = _now()
    await db.commit()
    return {"ok": True, "id": reserva.id}


# ─── Descartar ───
@router.post("/{reserva_id}/descartar")
async def descartar_reserva(
    reserva_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    razon = (data.get("razon") or "").strip()

    result = await db.execute(select(Reserva).where(Reserva.id == reserva_id))
    reserva = result.scalar_one_or_none()
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    reserva.estado = "descartada"
    reserva.descartada_at = _now()
    reserva.descarte_razon = razon
    await db.commit()
    return {"ok": True, "id": reserva.id}


# ─── Resumen del día (admin) ───
@router.get("/resumen-dia")
async def resumen_dia(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    hoy = datetime.now(TZ).date()
    inicio = datetime.combine(hoy, datetime.min.time())

    r_producidas = await db.execute(
        select(func.count(Reserva.id)).where(Reserva.created_at >= inicio)
    )
    producidas = r_producidas.scalar() or 0

    r_vendidas = await db.execute(
        select(func.count(Reserva.id)).where(Reserva.vendida_at >= inicio, Reserva.estado == "vendida")
    )
    vendidas = r_vendidas.scalar() or 0

    r_descartadas = await db.execute(
        select(func.count(Reserva.id)).where(Reserva.descartada_at >= inicio, Reserva.estado == "descartada")
    )
    descartadas = r_descartadas.scalar() or 0

    r_disponibles = await db.execute(
        select(func.count(Reserva.id)).where(Reserva.estado == "disponible")
    )
    disponibles_count = r_disponibles.scalar() or 0

    r_ingresos = await db.execute(
        select(func.sum(Reserva.precio)).where(Reserva.vendida_at >= inicio, Reserva.estado == "vendida")
    )
    ingresos = r_ingresos.scalar() or 0

    return {
        "producidas_hoy": producidas,
        "vendidas_hoy": vendidas,
        "descartadas_hoy": descartadas,
        "disponibles": disponibles_count,
        "ingresos_hoy": ingresos,
    }


# ─── Todas (admin con filtros) ───
@router.get("/todas")
async def todas(
    estado: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    query = select(Reserva).order_by(Reserva.created_at.desc()).limit(200)
    if estado:
        query = query.where(Reserva.estado == estado)
    result = await db.execute(query)
    reservas = result.scalars().all()
    return [await _serializar_reserva(r, db) for r in reservas]
