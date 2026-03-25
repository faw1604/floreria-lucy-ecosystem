from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.pagos import MetodoPago
from app.routers.auth import verificar_sesion

router = APIRouter()

@router.get("/cuenta-activa")
async def get_cuenta_activa(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MetodoPago)
        .where(MetodoPago.tipo == "transferencia")
        .where(MetodoPago.activo == True)
        .limit(1)
    )
    cuenta = result.scalar_one_or_none()
    if not cuenta:
        raise HTTPException(status_code=404, detail="No hay cuenta activa para transferencia")
    return {"banco": cuenta.banco, "titular": cuenta.titular, "clabe": cuenta.clabe}

@router.get("/oxxo")
async def get_datos_oxxo(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MetodoPago)
        .where(MetodoPago.tipo == "oxxo")
        .where(MetodoPago.activo == True)
        .limit(1)
    )
    oxxo = result.scalar_one_or_none()
    if not oxxo:
        raise HTTPException(status_code=404, detail="No hay datos OXXO configurados")
    return {"numero_tarjeta": oxxo.numero_tarjeta, "titular": oxxo.titular}

@router.get("/")
async def listar_metodos(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(MetodoPago))
    metodos = result.scalars().all()
    return [{"id": m.id, "tipo": m.tipo, "banco": m.banco, "titular": m.titular, "activo": m.activo, "solo_sucursal": m.solo_sucursal} for m in metodos]

@router.patch("/{metodo_id}/activar")
async def activar_metodo(
    metodo_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(MetodoPago).where(MetodoPago.id == metodo_id))
    metodo = result.scalar_one_or_none()
    if not metodo:
        raise HTTPException(status_code=404, detail="Método no encontrado")
    if metodo.tipo == "transferencia":
        await db.execute(
            select(MetodoPago).where(MetodoPago.tipo == "transferencia")
        )
        all_result = await db.execute(select(MetodoPago).where(MetodoPago.tipo == "transferencia"))
        for m in all_result.scalars().all():
            m.activo = False
    metodo.activo = request.get("activo", True)
    await db.commit()
    return {"id": metodo.id, "activo": metodo.activo}

@router.post("/")
async def crear_metodo(
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    metodo = MetodoPago(
        tipo=request.get("tipo", "transferencia"),
        banco=request.get("banco"),
        titular=request.get("titular"),
        clabe=request.get("clabe"),
        numero_tarjeta=request.get("numero_tarjeta"),
        activo=request.get("activo", True),
        solo_sucursal=request.get("solo_sucursal", False),
    )
    db.add(metodo)
    await db.commit()
    await db.refresh(metodo)
    return {"id": metodo.id, "tipo": metodo.tipo}
