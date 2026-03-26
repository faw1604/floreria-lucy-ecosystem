from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.inventario import InsumoFloral, InsumoNoFloral
from app.routers.auth import verificar_sesion

router = APIRouter()


@router.get("/floral")
async def listar_insumos_florales(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(InsumoFloral).order_by(InsumoFloral.categoria, InsumoFloral.familia, InsumoFloral.variante))
    items = result.scalars().all()
    return [{"id": i.id, "familia": i.familia, "variante": i.variante, "categoria": i.categoria, "stock_estado": i.stock_estado, "cantidad": i.cantidad, "descuento_automatico": i.descuento_automatico} for i in items]


@router.get("/no-floral")
async def listar_insumos_no_florales(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(InsumoNoFloral).order_by(InsumoNoFloral.categoria, InsumoNoFloral.variante))
    items = result.scalars().all()
    return [{"id": i.id, "categoria": i.categoria, "variante": i.variante, "stock_estado": i.stock_estado, "cantidad": i.cantidad} for i in items]


@router.patch("/floral/{item_id}")
async def actualizar_insumo_floral(
    item_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(InsumoFloral).where(InsumoFloral.id == item_id))
    insumo = result.scalar_one_or_none()
    if not insumo:
        raise HTTPException(status_code=404, detail="Insumo no encontrado")
    if "cantidad" in request:
        insumo.cantidad = request["cantidad"]
    if "stock_estado" in request:
        insumo.stock_estado = request["stock_estado"]
    await db.commit()
    return {"id": insumo.id, "familia": insumo.familia, "variante": insumo.variante, "cantidad": insumo.cantidad, "stock_estado": insumo.stock_estado}


@router.patch("/no-floral/{item_id}")
async def actualizar_insumo_no_floral(
    item_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(InsumoNoFloral).where(InsumoNoFloral.id == item_id))
    insumo = result.scalar_one_or_none()
    if not insumo:
        raise HTTPException(status_code=404, detail="Insumo no encontrado")
    if "cantidad" in request:
        insumo.cantidad = request["cantidad"]
    if "stock_estado" in request:
        insumo.stock_estado = request["stock_estado"]
    await db.commit()
    return {"id": insumo.id, "categoria": insumo.categoria, "variante": insumo.variante, "cantidad": insumo.cantidad, "stock_estado": insumo.stock_estado}


@router.get("/floral/disponibles")
async def insumos_florales_disponibles(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InsumoFloral).where(InsumoFloral.cantidad > 0).order_by(InsumoFloral.categoria, InsumoFloral.familia)
    )
    items = result.scalars().all()
    return [{"id": i.id, "familia": i.familia, "variante": i.variante, "categoria": i.categoria, "cantidad": i.cantidad} for i in items]
