from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from app.database import get_db
from app.models.pedidos import Pedido, ItemPedido
from app.core.config import TZ
from app.routers.auth import verificar_sesion

router = APIRouter()

async def generar_numero_pedido(db: AsyncSession) -> str:
    ahora = datetime.now(TZ)
    año = ahora.strftime("%Y")
    result = await db.execute(select(Pedido).where(Pedido.numero.like(f"FL-{año}-%")))
    count = len(result.scalars().all())
    return f"FL-{año}-{str(count + 1).zfill(4)}"

@router.get("/")
async def listar_pedidos(
    estado: str | None = None,
    fecha: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    query = select(Pedido).order_by(Pedido.fecha_pedido.desc())
    if estado:
        query = query.where(Pedido.estado == estado)
    result = await db.execute(query)
    pedidos = result.scalars().all()
    return [{"id": p.id, "numero": p.numero, "estado": p.estado, "canal": p.canal, "total": p.total, "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None, "horario_entrega": p.horario_entrega, "receptor_nombre": p.receptor_nombre, "requiere_humano": p.requiere_humano} for p in pedidos]

@router.get("/hoy")
async def pedidos_del_dia(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    hoy = datetime.now(TZ).date()
    result = await db.execute(
        select(Pedido)
        .where(Pedido.fecha_entrega == hoy)
        .order_by(Pedido.horario_entrega)
    )
    pedidos = result.scalars().all()
    return [{"id": p.id, "numero": p.numero, "estado": p.estado, "canal": p.canal, "total": p.total, "horario_entrega": p.horario_entrega, "hora_exacta": p.hora_exacta, "receptor_nombre": p.receptor_nombre, "receptor_telefono": p.receptor_telefono, "direccion_entrega": p.direccion_entrega, "dedicatoria": p.dedicatoria, "notas_internas": p.notas_internas, "requiere_humano": p.requiere_humano, "tipo_especial": p.tipo_especial} for p in pedidos]

@router.get("/{pedido_id}")
async def obtener_pedido(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return pedido

@router.post("/")
async def crear_pedido(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    numero = await generar_numero_pedido(db)
    pedido = Pedido(
        numero=numero,
        customer_id=request.get("customer_id"),
        canal=request.get("canal", "WhatsApp"),
        estado=request.get("estado", "Nuevo"),
        fecha_entrega=request.get("fecha_entrega"),
        horario_entrega=request.get("horario_entrega"),
        hora_exacta=request.get("hora_exacta"),
        zona_entrega=request.get("zona_entrega"),
        direccion_entrega=request.get("direccion_entrega"),
        receptor_nombre=request.get("receptor_nombre"),
        receptor_telefono=request.get("receptor_telefono"),
        dedicatoria=request.get("dedicatoria"),
        notas_internas=request.get("notas_internas"),
        forma_pago=request.get("forma_pago"),
        pago_confirmado=request.get("pago_confirmado", False),
        subtotal=request.get("subtotal", 0),
        envio=request.get("envio", 0),
        total=request.get("total", 0),
        requiere_humano=request.get("requiere_humano", False),
        tipo_especial=request.get("tipo_especial"),
    )
    db.add(pedido)
    await db.commit()
    await db.refresh(pedido)
    return {"id": pedido.id, "numero": pedido.numero, "estado": pedido.estado}

@router.patch("/{pedido_id}/estado")
async def actualizar_estado(
    pedido_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    pedido.estado = request.get("estado", pedido.estado)
    pedido.pago_confirmado = request.get("pago_confirmado", pedido.pago_confirmado)
    await db.commit()
    return {"id": pedido.id, "numero": pedido.numero, "estado": pedido.estado}
