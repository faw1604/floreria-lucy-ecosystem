from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.clientes import Cliente
from app.routers.auth import verificar_sesion
from app.core.security import generar_codigo_referido
from datetime import date
import re

router = APIRouter()


def limpiar_telefono(tel: str) -> str:
    """Remove +52, 521, or country prefix from phone."""
    digits = re.sub(r"\D", "", tel)
    if digits.startswith("521") and len(digits) > 10:
        digits = digits[3:]
    elif digits.startswith("52") and len(digits) > 10:
        digits = digits[2:]
    return digits


@router.get("/")
async def listar_clientes(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Cliente).order_by(Cliente.nombre))
    clientes = result.scalars().all()
    return [{"id": c.id, "nombre": c.nombre, "telefono": c.telefono, "fuente": c.fuente, "codigo_referido": c.codigo_referido, "registrado_web": c.registrado_web} for c in clientes]


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
    fecha_aniv_str = request.get("fecha_aniversario")
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

    fecha_aniv = None
    if fecha_aniv_str:
        try:
            fecha_aniv = date.fromisoformat(fecha_aniv_str)
        except ValueError:
            pass

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
        if fecha_aniv:
            cliente.fecha_aniversario = fecha_aniv
        if not cliente.codigo_referido:
            cliente.codigo_referido = generar_codigo_referido(cliente.nombre, cliente.telefono)
    else:
        codigo = generar_codigo_referido(nombre, telefono)
        cliente = Cliente(
            nombre=nombre,
            telefono=telefono,
            email=email,
            fecha_nacimiento=fecha_nac,
            fecha_aniversario=fecha_aniv,
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
