from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.clientes import Cliente
from app.routers.auth import verificar_sesion
from fastapi import Cookie

router = APIRouter()

@router.get("/")
async def listar_clientes(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Cliente).order_by(Cliente.nombre))
    clientes = result.scalars().all()
    return [{"id": c.id, "nombre": c.nombre, "telefono": c.telefono, "fuente": c.fuente} for c in clientes]

@router.get("/buscar")
async def buscar_cliente_por_telefono(
    telefono: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Cliente).where(Cliente.telefono == telefono))
    cliente = result.scalar_one_or_none()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"id": cliente.id, "nombre": cliente.nombre, "telefono": cliente.telefono, "direccion_default": cliente.direccion_default}

@router.post("/")
async def crear_cliente(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    from fastapi import Request
    cliente = Cliente(
        nombre=request.get("nombre", ""),
        telefono=request.get("telefono", ""),
        direccion_default=request.get("direccion_default"),
        email=request.get("email"),
        fuente=request.get("fuente", "WhatsApp"),
    )
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return {"id": cliente.id, "nombre": cliente.nombre, "telefono": cliente.telefono}
