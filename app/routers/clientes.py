from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.clientes import Cliente
from app.models.pedidos import Pedido
from app.routers.auth import verificar_sesion
from app.core.security import generar_codigo_referido
from app.core.utils import limpiar_telefono
from datetime import date
from sqlalchemy import func
import json

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
    return [{"id": c.id, "nombre": c.nombre, "telefono": c.telefono, "email": c.email, "fuente": c.fuente, "codigo_referido": c.codigo_referido, "registrado_web": c.registrado_web, "direccion_default": c.direccion_default, "total_pedidos": 0, "total_gastado": 0} for c in clientes]


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


@router.get("/verificar")
async def verificar_cliente(
    telefono: str,
    db: AsyncSession = Depends(get_db)
):
    tel = limpiar_telefono(telefono)
    result = await db.execute(select(Cliente).where(Cliente.telefono == tel))
    cliente = result.scalar_one_or_none()
    if cliente:
        return {
            "existe": True,
            "nombre": cliente.nombre,
            "cliente_id": cliente.id,
            "descuento_primera_compra": cliente.descuento_primera_compra,
            "codigo_referido": cliente.codigo_referido,
            "descuento_referido": cliente.descuento_referido,
        }
    return {"existe": False, "nombre": None}


@router.post("/registro-web")
async def registro_web(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    nombre = (request.get("nombre") or "").strip()
    telefono_raw = (request.get("telefono") or "").strip()
    email = (request.get("email") or "").strip() or None
    fecha_nac_str = request.get("fecha_nacimiento")
    fechas_especiales = request.get("fechas_especiales") or []
    codigo_usado = (request.get("codigo_referido_usado") or "").strip().upper() or None

    if not nombre or not telefono_raw:
        raise HTTPException(status_code=400, detail="Nombre y teléfono son obligatorios")

    telefono = limpiar_telefono(telefono_raw)

    fecha_nac = None
    if fecha_nac_str:
        try:
            fecha_nac = date.fromisoformat(fecha_nac_str)
        except ValueError:
            pass

    # Serialize fechas_especiales as JSON
    fechas_json = None
    if fechas_especiales and isinstance(fechas_especiales, list):
        valid = [f for f in fechas_especiales if f.get("nombre") and f.get("fecha")]
        if valid:
            fechas_json = json.dumps(valid, ensure_ascii=False)

    # Check if client already exists
    result = await db.execute(select(Cliente).where(Cliente.telefono == telefono))
    cliente = result.scalar_one_or_none()
    ya_existia = cliente is not None

    if cliente:
        # Update with new data (don't overwrite with empty)
        if email:
            cliente.email = email
        if fecha_nac:
            cliente.fecha_nacimiento = fecha_nac
        if fechas_json:
            cliente.fechas_especiales = fechas_json
        if not cliente.codigo_referido:
            cliente.codigo_referido = generar_codigo_referido(cliente.nombre, cliente.telefono)
    else:
        codigo = generar_codigo_referido(nombre, telefono)
        cliente = Cliente(
            nombre=nombre,
            telefono=telefono,
            email=email,
            fecha_nacimiento=fecha_nac,
            fechas_especiales=fechas_json,
            fuente="Web",
            registrado_web=True,
            codigo_referido=codigo,
            descuento_primera_compra=True,
        )
        db.add(cliente)

    # Handle referral code
    if codigo_usado and not cliente.referido_por:
        ref_result = await db.execute(
            select(Cliente).where(Cliente.codigo_referido == codigo_usado)
        )
        referrer = ref_result.scalar_one_or_none()
        if referrer and referrer.id != (cliente.id if ya_existia else 0):
            cliente.referido_por = codigo_usado
            referrer.descuento_referido = (referrer.descuento_referido or 0) + 5000  # $50 per referral

    await db.commit()
    await db.refresh(cliente)

    return {
        "ok": True,
        "cliente_id": cliente.id,
        "nombre": cliente.nombre,
        "codigo_referido": cliente.codigo_referido,
        "descuento_primera_compra": cliente.descuento_primera_compra,
        "ya_existia": ya_existia,
        "mensaje": f"{'¡Hola de nuevo' if ya_existia else '¡Bienvenid@'} {cliente.nombre.split()[0]}! Tu código de referido es {cliente.codigo_referido}",
    }


@router.get("/{cliente_id}/descuentos")
async def descuentos_cliente(
    cliente_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    cliente = result.scalar_one_or_none()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {
        "descuento_primera_compra": cliente.descuento_primera_compra,
        "porcentaje_primera_compra": 10 if cliente.descuento_primera_compra else 0,
        "descuento_referido": cliente.descuento_referido or 0,
        "descuento_referido_display": f"${(cliente.descuento_referido or 0) // 100}",
    }


@router.get("/{cliente_id}/referidos")
async def referidos_cliente(
    cliente_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    cliente = result.scalar_one_or_none()
    if not cliente or not cliente.codigo_referido:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    ref_result = await db.execute(
        select(Cliente).where(Cliente.referido_por == cliente.codigo_referido)
    )
    referidos = ref_result.scalars().all()
    return {
        "codigo_referido": cliente.codigo_referido,
        "total_referidos": len(referidos),
        "descuento_acumulado": cliente.descuento_referido or 0,
        "descuento_acumulado_display": f"${(cliente.descuento_referido or 0) // 100}",
        "referidos": [{"nombre": r.nombre, "telefono": r.telefono, "fecha": str(r.creado_en.date()) if r.creado_en else None} for r in referidos],
    }


@router.post("/{cliente_id}/usar-descuento-referido")
async def usar_descuento_referido(
    cliente_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    cliente = result.scalar_one_or_none()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    monto = request.get("monto", cliente.descuento_referido or 0)
    if monto > (cliente.descuento_referido or 0):
        raise HTTPException(status_code=400, detail="Monto excede descuento disponible")
    cliente.descuento_referido = (cliente.descuento_referido or 0) - monto
    await db.commit()
    return {
        "ok": True,
        "descuento_aplicado": monto,
        "descuento_restante": cliente.descuento_referido,
    }


@router.post("/")
async def crear_cliente(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    nombre = (request.get("nombre") or "").strip()
    telefono = limpiar_telefono(request.get("telefono") or "")
    if not nombre or not telefono:
        raise HTTPException(status_code=400, detail="Nombre y teléfono son obligatorios")
    # Si ya existe un cliente con ese teléfono, devolverlo en vez de duplicar
    existing = await db.execute(select(Cliente).where(Cliente.telefono == telefono))
    cliente = existing.scalar_one_or_none()
    if cliente:
        return {"id": cliente.id, "nombre": cliente.nombre, "telefono": cliente.telefono, "ya_existia": True}
    cliente = Cliente(
        nombre=nombre,
        telefono=telefono,
        direccion_default=request.get("direccion_default"),
        email=request.get("email"),
        fuente=request.get("fuente", "WhatsApp"),
    )
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return {"id": cliente.id, "nombre": cliente.nombre, "telefono": cliente.telefono, "ya_existia": False}


@router.get("/{cliente_id}")
async def obtener_cliente(
    cliente_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"id": c.id, "nombre": c.nombre, "telefono": c.telefono, "email": c.email, "direccion_default": c.direccion_default, "fuente": c.fuente}


@router.put("/{cliente_id}")
async def actualizar_cliente(
    cliente_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    for campo in ["nombre", "telefono", "email", "direccion_default"]:
        if campo in request:
            valor = request[campo]
            if campo == "telefono" and valor:
                valor = limpiar_telefono(valor)
                # Verificar que el nuevo teléfono no esté en uso por otro cliente
                dup = await db.execute(
                    select(Cliente).where(Cliente.telefono == valor, Cliente.id != cliente_id)
                )
                if dup.scalar_one_or_none():
                    raise HTTPException(status_code=400, detail="Ese teléfono ya está en uso por otro cliente")
            setattr(c, campo, valor)
    await db.commit()
    return {"ok": True, "id": c.id}


@router.delete("/{cliente_id}")
async def eliminar_cliente(
    cliente_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    # No permitir eliminar si tiene pedidos asociados (los conservamos para historial / recuperación)
    pedidos_r = await db.execute(
        select(func.count(Pedido.id)).where(Pedido.customer_id == cliente_id)
    )
    n_pedidos = pedidos_r.scalar() or 0
    if n_pedidos > 0:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar: el cliente tiene {n_pedidos} pedido(s) en su historial",
        )
    await db.delete(c)
    await db.commit()
    return {"ok": True}
