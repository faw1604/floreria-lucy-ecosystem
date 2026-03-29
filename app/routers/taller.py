from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, date as date_type
import logging

from app.database import get_db
from app.models.pedidos import Pedido, ItemPedido
from app.models.clientes import Cliente
from app.models.productos import Producto
from app.models.configuracion import ConfiguracionNegocio
from app.models.inventario import InsumoFloral, InsumoProducto
from app.core.config import TZ
from app.routers.auth import verificar_sesion

logger = logging.getLogger("floreria")

router = APIRouter()

def _now():
    """Datetime actual en Chihuahua, sin timezone (naive) para asyncpg."""
    return datetime.now(TZ).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _serializar_pedido_taller(p, db: AsyncSession) -> dict:
    """Serializa un pedido con toda la info necesaria para el KDS del taller."""
    # Items
    result = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == p.id))
    items_db = result.scalars().all()
    items = []
    for item in items_db:
        prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
        prod = prod_result.scalar_one_or_none()
        items.append({
            "nombre": prod.nombre if prod else "Producto eliminado",
            "codigo": prod.codigo if prod else None,
            "imagen_url": prod.imagen_url if prod else None,
            "cantidad": item.cantidad,
            "es_personalizado": item.es_personalizado,
            "nombre_personalizado": item.nombre_personalizado,
            "observaciones": item.observaciones,
        })

    # Cliente
    cliente_nombre = None
    cliente_telefono = None
    if p.customer_id:
        cli_result = await db.execute(select(Cliente).where(Cliente.id == p.customer_id))
        cliente = cli_result.scalar_one_or_none()
        if cliente:
            cliente_nombre = cliente.nombre
            cliente_telefono = cliente.telefono

    return {
        "id": p.id,
        "numero": p.numero,
        "estado": p.estado,
        "canal": p.canal,
        "total": p.total,
        "subtotal": p.subtotal,
        "envio": p.envio,
        "horario_entrega": p.horario_entrega,
        "hora_exacta": p.hora_exacta,
        "receptor_nombre": p.receptor_nombre,
        "receptor_telefono": p.receptor_telefono,
        "direccion_entrega": p.direccion_entrega,
        "dedicatoria": p.dedicatoria,
        "notas_internas": p.notas_internas,
        "tipo_especial": p.tipo_especial,
        "pago_confirmado": p.pago_confirmado,
        "zona_entrega": p.zona_entrega,
        "forma_pago": p.forma_pago,
        "estado_florista": p.estado_florista,
        "nota_florista": p.nota_florista,
        "requiere_factura": p.requiere_factura,
        "metodo_entrega": p.metodo_entrega,
        "ruta": p.ruta,
        "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None,
        "fecha_pedido": p.fecha_pedido.isoformat() if p.fecha_pedido else None,
        "produccion_at": p.produccion_at.isoformat() if p.produccion_at else None,
        "listo_at": p.listo_at.isoformat() if p.listo_at else None,
        "entregado_at": p.entregado_at.isoformat() if p.entregado_at else None,
        "cliente_nombre": cliente_nombre,
        "cliente_telefono": cliente_telefono,
        "items": items,
    }


def _auth(panel_session: str | None):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")


# ---------------------------------------------------------------------------
# Badge counts (polling every 15s)
# ---------------------------------------------------------------------------

@router.get("/badges")
async def badges(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    hoy = datetime.now(TZ).date()

    r_nuevos = await db.execute(
        select(func.count(Pedido.id)).where(Pedido.estado == "esperando_validacion")
    )
    nuevos = r_nuevos.scalar() or 0

    r_prod = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.estado.in_(["En producción", "pagado"]),
            Pedido.fecha_entrega == hoy,
        )
    )
    produccion = r_prod.scalar() or 0

    r_recoger = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.estado.in_(["Listo", "listo_taller"]),
            Pedido.metodo_entrega.in_(["recoger", "funeral_recoger"]),
        )
    )
    por_recoger = r_recoger.scalar() or 0

    return {"nuevos": nuevos, "produccion": produccion, "por_recoger": por_recoger}


# ---------------------------------------------------------------------------
# Tab data endpoints
# ---------------------------------------------------------------------------

@router.get("/nuevos")
async def nuevos(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    from sqlalchemy import or_
    # esperando_validacion (WhatsApp/Web) + pendiente_pago sin aprobar (POS)
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(["esperando_validacion", "pendiente_pago", "Pendiente pago"]),
            or_(
                Pedido.estado_florista.is_(None),
                Pedido.estado_florista == "pendiente_aprobacion",
                Pedido.estado_florista == "aprobado_con_modificacion",
                Pedido.estado_florista == "cambio_sugerido",
                Pedido.estado_florista == "rechazado",
                Pedido.estado_florista == "requiere_atencion",
            ),
        )
        .order_by(Pedido.fecha_pedido.desc())
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/produccion/hoy")
async def produccion_hoy(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    hoy = datetime.now(TZ).date()
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(["En producción", "pagado"]),
            Pedido.fecha_entrega == hoy,
        )
        .order_by(Pedido.horario_entrega, Pedido.hora_exacta)
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/produccion/manana")
async def produccion_manana(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    manana = datetime.now(TZ).date() + timedelta(days=1)
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(["En producción", "pagado"]),
            Pedido.fecha_entrega == manana,
        )
        .order_by(Pedido.horario_entrega, Pedido.hora_exacta)
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/por-recoger")
async def por_recoger(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(["Listo", "listo_taller"]),
            Pedido.metodo_entrega.in_(["recoger", "funeral_recoger"]),
        )
        .order_by(Pedido.fecha_entrega, Pedido.horario_entrega)
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/proximos")
async def proximos(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    manana = datetime.now(TZ).date() + timedelta(days=1)
    result = await db.execute(
        select(Pedido)
        .where(Pedido.fecha_entrega > manana)
        .order_by(Pedido.fecha_entrega, Pedido.horario_entrega)
    )
    pedidos = result.scalars().all()
    # Group by date
    grouped: dict[str, list] = {}
    for p in pedidos:
        key = str(p.fecha_entrega) if p.fecha_entrega else "sin_fecha"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(await _serializar_pedido_taller(p, db))
    return grouped


@router.get("/realizados")
async def realizados(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    hoy = datetime.now(TZ).date()
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(["Entregado", "entregado"]),
            Pedido.fecha_entrega == hoy,
        )
        .order_by(Pedido.entregado_at.desc())
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


# ---------------------------------------------------------------------------
# Action endpoints
# ---------------------------------------------------------------------------

async def _get_pedido(pedido_id: int, db: AsyncSession) -> Pedido:
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return pedido


@router.post("/pedidos/{pedido_id}/aceptar")
async def aceptar(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    pedido = await _get_pedido(pedido_id, db)
    pedido.estado = "En producción"
    pedido.estado_florista = "aprobado"
    pedido.produccion_at = _now()

    # Auto-descuento de inventario para insumos con descuento_automatico=true
    items_result = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == pedido.id))
    items_pedido = items_result.scalars().all()
    for item in items_pedido:
        insumos_result = await db.execute(
            select(InsumoProducto).where(InsumoProducto.producto_id == item.producto_id)
        )
        for ip in insumos_result.scalars().all():
            if ip.insumo_floral_id:
                insumo_result = await db.execute(
                    select(InsumoFloral).where(
                        InsumoFloral.id == ip.insumo_floral_id,
                        InsumoFloral.descuento_automatico == True,
                    )
                )
                insumo = insumo_result.scalar_one_or_none()
                if insumo and insumo.cantidad > 0:
                    insumo.cantidad = max(0, insumo.cantidad - ip.cantidad_consumida * item.cantidad)

    await db.commit()
    return {"ok": True, "id": pedido.id, "estado": pedido.estado}


@router.post("/pedidos/{pedido_id}/aceptar-con-cambios")
async def aceptar_con_cambios(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    nota = data.get("nota", "")
    pedido = await _get_pedido(pedido_id, db)
    pedido.estado = "En producción"
    pedido.estado_florista = "aprobado_con_modificacion"
    pedido.nota_florista = nota
    pedido.produccion_at = _now()
    await db.commit()
    return {"ok": True, "id": pedido.id, "estado": pedido.estado}


@router.post("/pedidos/{pedido_id}/sugerir-cambio")
async def sugerir_cambio(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    nota = data.get("nota", "")
    pedido = await _get_pedido(pedido_id, db)
    pedido.estado_florista = "cambio_sugerido"
    pedido.nota_florista = nota
    await db.commit()
    return {"ok": True, "id": pedido.id, "estado_florista": pedido.estado_florista}


@router.post("/pedidos/{pedido_id}/no-aceptar")
async def no_aceptar(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    razon = data.get("razon", "")
    pedido = await _get_pedido(pedido_id, db)
    pedido.estado_florista = "rechazado"
    pedido.nota_florista = razon
    pedido.requiere_humano = True
    await db.commit()
    return {"ok": True, "id": pedido.id, "estado_florista": pedido.estado_florista}


@router.post("/pedidos/{pedido_id}/cancelar")
async def cancelar(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    razon = data.get("razon", "")
    pedido = await _get_pedido(pedido_id, db)
    pedido.estado = "Cancelado"
    pedido.cancelado_razon = razon
    await db.commit()
    return {"ok": True, "id": pedido.id, "estado": pedido.estado}


@router.post("/pedidos/{pedido_id}/listo")
async def listo(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    pedido = await _get_pedido(pedido_id, db)
    pedido.estado = "listo_taller"
    pedido.listo_at = _now()
    await db.commit()
    return {"ok": True, "id": pedido.id, "estado": pedido.estado}


@router.post("/pedidos/{pedido_id}/entregado")
async def entregado(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    pedido = await _get_pedido(pedido_id, db)
    pedido.estado = "Entregado"
    pedido.entregado_at = _now()
    await db.commit()
    return {"ok": True, "id": pedido.id, "estado": pedido.estado}


# ---------------------------------------------------------------------------
# Print endpoints
# ---------------------------------------------------------------------------

async def _generar_etiqueta(pedido: Pedido, db: AsyncSession, item_index: int | None = None) -> str:
    """Genera texto de etiqueta para impresión."""
    # Cliente
    cliente_nombre = ""
    if pedido.customer_id:
        cli_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
        cliente = cli_result.scalar_one_or_none()
        if cliente:
            cliente_nombre = cliente.nombre

    # Items
    result = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == pedido.id))
    items_db = result.scalars().all()

    if item_index is not None and 0 <= item_index < len(items_db):
        items_db = [items_db[item_index]]

    lineas = [
        "================================",
        "       FLORERIA LUCY",
        "================================",
        f"Pedido: {pedido.numero}",
        f"Fecha entrega: {pedido.fecha_entrega or 'Sin fecha'}",
        f"Horario: {pedido.horario_entrega or ''} {pedido.hora_exacta or ''}".strip(),
        f"Canal: {pedido.canal or ''}",
        "--------------------------------",
    ]

    if pedido.receptor_nombre:
        lineas.append(f"Para: {pedido.receptor_nombre}")
    if pedido.receptor_telefono:
        lineas.append(f"Tel: {pedido.receptor_telefono}")
    if pedido.direccion_entrega:
        lineas.append(f"Dir: {pedido.direccion_entrega}")
    if pedido.zona_entrega:
        lineas.append(f"Zona: {pedido.zona_entrega}")
    if pedido.ruta:
        lineas.append(f"Ruta: {pedido.ruta}")
    if pedido.metodo_entrega:
        lineas.append(f"Entrega: {pedido.metodo_entrega}")

    lineas.append("--------------------------------")
    lineas.append("PRODUCTOS:")

    for item in items_db:
        prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
        prod = prod_result.scalar_one_or_none()
        nombre = item.nombre_personalizado if item.es_personalizado and item.nombre_personalizado else (prod.nombre if prod else "Producto")
        lineas.append(f"  {item.cantidad}x {nombre}")
        if item.observaciones:
            lineas.append(f"     Obs: {item.observaciones}")

    if pedido.dedicatoria:
        lineas.append("--------------------------------")
        lineas.append(f"Dedicatoria: {pedido.dedicatoria}")

    if pedido.notas_internas:
        lineas.append("--------------------------------")
        lineas.append(f"Notas: {pedido.notas_internas}")

    lineas.append("================================")
    lineas.append(f"Cliente: {cliente_nombre}")
    lineas.append("================================")

    return "\n".join(lineas)


@router.post("/imprimir-etiqueta")
async def imprimir_etiqueta(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    pedido_id = data.get("pedido_id")
    item_index = data.get("item_index")
    if not pedido_id:
        raise HTTPException(status_code=400, detail="pedido_id requerido")
    pedido = await _get_pedido(pedido_id, db)
    texto = await _generar_etiqueta(pedido, db, item_index)
    return PlainTextResponse(texto)


@router.post("/imprimir-etiquetas-manana")
async def imprimir_etiquetas_manana(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    manana = datetime.now(TZ).date() + timedelta(days=1)
    result = await db.execute(
        select(Pedido)
        .where(Pedido.fecha_entrega == manana)
        .order_by(Pedido.horario_entrega, Pedido.hora_exacta)
    )
    pedidos = result.scalars().all()
    etiquetas = []
    for p in pedidos:
        etiquetas.append(await _generar_etiqueta(p, db))
    texto = "\n\n".join(etiquetas)
    return PlainTextResponse(texto)


# ---------------------------------------------------------------------------
# Entregas (for POS and Admin)
# ---------------------------------------------------------------------------

@router.get("/entregas/lobby")
async def entregas_lobby(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(
        select(Pedido)
        .where(Pedido.estado.in_(["Listo", "listo_taller"]), Pedido.metodo_entrega == "mostrador")
        .order_by(Pedido.listo_at)
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/entregas/por-recoger")
async def entregas_por_recoger(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(["Listo", "listo_taller"]),
            Pedido.metodo_entrega.in_(["recoger", "funeral_recoger"]),
        )
        .order_by(Pedido.fecha_entrega, Pedido.horario_entrega)
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/entregas/envios")
async def entregas_envios(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(["Listo", "listo_taller", "En camino"]),
            Pedido.metodo_entrega.in_(["envio", "funeral_envio"]),
        )
        .order_by(Pedido.fecha_entrega, Pedido.horario_entrega)
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/entregas/resumen-dia")
async def entregas_resumen_dia(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    hoy = datetime.now(TZ).date()

    r_total = await db.execute(
        select(func.count(Pedido.id)).where(Pedido.fecha_entrega == hoy)
    )
    total = r_total.scalar() or 0

    r_entregados = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.fecha_entrega == hoy,
            Pedido.estado.in_(["Entregado", "entregado"]),
        )
    )
    entregados = r_entregados.scalar() or 0

    r_pendientes = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.fecha_entrega == hoy,
            Pedido.estado.notin_(["Entregado", "entregado", "Cancelado"]),
        )
    )
    pendientes = r_pendientes.scalar() or 0

    r_repartidores = await db.execute(
        select(func.count(func.distinct(Pedido.ruta))).where(
            Pedido.fecha_entrega == hoy,
            Pedido.estado == "En camino",
            Pedido.ruta.isnot(None),
        )
    )
    repartidores_activos = r_repartidores.scalar() or 0

    return {
        "total": total,
        "entregados": entregados,
        "pendientes": pendientes,
        "repartidores_activos": repartidores_activos,
    }


# ---------------------------------------------------------------------------
# Fecha fuerte config
# ---------------------------------------------------------------------------

@router.get("/fecha-fuerte/config")
async def fecha_fuerte_config(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    # Get all fecha_fuerte_* keys from configuracion_negocio
    result = await db.execute(
        select(ConfiguracionNegocio).where(
            ConfiguracionNegocio.clave.like("fecha_fuerte_%")
        )
    )
    rows = result.scalars().all()
    config = {r.clave: r.valor for r in rows}
    return config


@router.post("/fecha-fuerte/lote/{lote}/listo")
async def fecha_fuerte_lote_listo(
    lote: str,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    ahora = _now()

    # Mark all pedidos in this batch as Listo
    result = await db.execute(
        select(Pedido).where(
            Pedido.modo_fecha_fuerte_lote == lote,
            Pedido.estado.in_(["En producción", "pagado"]),
        )
    )
    pedidos = result.scalars().all()
    if not pedidos:
        raise HTTPException(status_code=404, detail=f"No se encontraron pedidos en lote '{lote}'")

    ids = []
    for p in pedidos:
        p.estado = "Listo"
        p.listo_at = ahora
        ids.append(p.id)

    await db.commit()
    return {"ok": True, "lote": lote, "pedidos_actualizados": ids}
