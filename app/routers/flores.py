from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.flores import TipoFlor
from app.routers.auth import verificar_sesion

router = APIRouter()

@router.get("/")
async def listar_flores(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TipoFlor).order_by(TipoFlor.nombre))
    flores = result.scalars().all()
    return [{"id": f.id, "nombre": f.nombre, "disponible_hoy": f.disponible_hoy, "costo_unitario": f.costo_unitario} for f in flores]

@router.patch("/{flor_id}/disponibilidad")
async def actualizar_disponibilidad(
    flor_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(TipoFlor).where(TipoFlor.id == flor_id))
    flor = result.scalar_one_or_none()
    if not flor:
        raise HTTPException(status_code=404, detail="Flor no encontrada")
    flor.disponible_hoy = request.get("disponible_hoy", flor.disponible_hoy)
    await db.commit()
    return {"id": flor.id, "nombre": flor.nombre, "disponible_hoy": flor.disponible_hoy}

@router.post("/")
async def crear_flor(
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    flor = TipoFlor(
        nombre=request.get("nombre", ""),
        costo_unitario=request.get("costo_unitario", 0),
        disponible_hoy=request.get("disponible_hoy", True),
    )
    db.add(flor)
    await db.commit()
    await db.refresh(flor)
    return {"id": flor.id, "nombre": flor.nombre}
