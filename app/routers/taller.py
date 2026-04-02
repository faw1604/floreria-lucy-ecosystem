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
from app.core.utils import ahora, hoy
from app.core.estados import EstadoPedido as EP, EstadoFlorista as EF, MetodoEntrega as ME
from app.routers.auth import verificar_sesion

logger = logging.getLogger("floreria")

router = APIRouter()


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


async def _tel_cliente(pedido, db) -> str | None:
    """Obtiene teléfono del cliente asociado al pedido."""
    if pedido.customer_id:
        from app.models.clientes import Cliente
        r = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
        cli = r.scalar_one_or_none()
        return cli.telefono if cli else None
    return None


# ---------------------------------------------------------------------------
# Badge counts (polling every 15s)
# ---------------------------------------------------------------------------

@router.get("/badges")
async def badges(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    fecha_hoy = hoy()

    r_nuevos = await db.execute(
        select(func.count(Pedido.id)).where(Pedido.estado == EP.ESPERANDO_VALIDACION)
    )
    nuevos = r_nuevos.scalar() or 0

    r_prod = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.estado.in_(EP.EN_TALLER_PRODUCCION),
            Pedido.fecha_entrega == fecha_hoy,
        )
    )
    produccion = r_prod.scalar() or 0

    r_recoger = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.estado.in_(EP.LISTOS),
            Pedido.metodo_entrega.in_(ME.PARA_RECOGER),
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
            Pedido.estado.in_(EP.EN_TALLER_NUEVOS),
            or_(
                Pedido.estado_florista.is_(None),
                Pedido.estado_florista == EF.PENDIENTE,
                Pedido.estado_florista == EF.APROBADO_CON_MODIFICACION,
                Pedido.estado_florista == EF.CAMBIO_SUGERIDO,
                Pedido.estado_florista == EF.RECHAZADO,
                Pedido.estado_florista == EF.REQUIERE_ATENCION,
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
    fecha_hoy = hoy()
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(EP.EN_TALLER_PRODUCCION),
            Pedido.fecha_entrega == fecha_hoy,
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
    manana = hoy() + timedelta(days=1)
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(EP.EN_TALLER_PRODUCCION),
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
            Pedido.estado.in_(EP.LISTOS),
            Pedido.metodo_entrega.in_(ME.PARA_RECOGER),
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
    manana = hoy() + timedelta(days=1)
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
    fecha: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    f = _parse_fecha(fecha) or hoy()
    result = await db.execute(
        select(Pedido)
        .where(
            Pedido.estado.in_(EP.FINALIZADOS + [EP.LISTO_TALLER, EP.EN_CAMINO]),
            Pedido.fecha_entrega == f,
        )
        .order_by(Pedido.entregado_at.desc().nulls_last(), Pedido.fecha_pedido.desc())
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

    # Web/WhatsApp sin pagar → pendiente_pago (falta cobrar)
    # POS o ya pagado → En producción (directo al taller)
    if pedido.pago_confirmado or pedido.canal == "Mostrador":
        pedido.estado = EP.EN_PRODUCCION
        pedido.produccion_at = ahora()
    else:
        pedido.estado = EP.PENDIENTE_PAGO

    pedido.estado_florista = EF.APROBADO

    # Auto-descuento solo si entra a producción
    if pedido.estado == EP.EN_PRODUCCION:
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

    # Webhook / WhatsApp al aceptar
    if pedido.webhook_url:
        from app.routers.pedidos import _disparar_webhook
        _disparar_webhook(pedido.webhook_url, pedido.numero, EP.ESPERANDO_VALIDACION, pedido.estado, extra={
            "accion": "florista_acepta",
            "telefono_cliente": await _tel_cliente(pedido, db),
            "fecha_entrega": str(pedido.fecha_entrega) if pedido.fecha_entrega else None,
        })
    elif pedido.tracking_token and pedido.customer_id and pedido.estado == EP.PENDIENTE_PAGO:
        # Pedido web aceptado — notificar en background
        try:
            from app.models.clientes import Cliente
            cliente_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cliente = cliente_result.scalar_one_or_none()
            if cliente and cliente.telefono:
                tracking_url = f"https://www.florerialucy.com/catalogo/seguimiento.html?token={pedido.tracking_token}"
                _tel = cliente.telefono
                _nombre = cliente.nombre.split()[0]
                _folio = pedido.numero
                import asyncio
                async def _send():
                    try:
                        from app.routers.catalogo import _enviar_whatsapp
                        await _enviar_whatsapp(_tel,
                            f"Hola {_nombre} 🌸\n\n"
                            f"Tu pedido {_folio} fue aceptado!\n\n"
                            f"Para proceder con el pago, como prefieres pagar?\n\n"
                            f"1. Transferencia bancaria\n"
                            f"2. Deposito en OXXO\n\n"
                            f"Puedes ver el estatus de tu pedido aqui:\n{tracking_url}"
                        )
                    except Exception:
                        pass
                asyncio.create_task(_send())
        except Exception:
            pass

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
    # No avanzar estado — esperar respuesta del cliente
    pedido.estado_florista = EF.APROBADO_CON_MODIFICACION
    pedido.nota_florista = nota
    await db.commit()

    # Webhook a Claudia (si es pedido de WhatsApp)
    if pedido.webhook_url:
        from app.routers.pedidos import _disparar_webhook
        _disparar_webhook(pedido.webhook_url, pedido.numero, pedido.estado, pedido.estado, extra={
            "accion": "florista_modifica",
            "nota": nota,
            "telefono_cliente": await _tel_cliente(pedido, db),
        })
    elif pedido.tracking_token and pedido.customer_id:
        # Pedido web — enviar WhatsApp directo
        try:
            from app.models.clientes import Cliente
            cliente_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cliente = cliente_result.scalar_one_or_none()
            if cliente and cliente.telefono:
                tracking_url = f"https://www.florerialucy.com/catalogo/seguimiento.html?token={pedido.tracking_token}"
                msg = (
                    f"Hola {cliente.nombre.split()[0]} 🌸\n\n"
                    f"Nuestro florista hizo una modificación a tu pedido {pedido.numero}:\n\n"
                    f"✏️ \"{nota}\"\n\n"
                    f"Revisa los detalles aquí:\n{tracking_url}"
                )
                from app.routers.catalogo import _enviar_whatsapp
                await _enviar_whatsapp(cliente.telefono, msg)
        except Exception as e:
            import logging
            logging.getLogger("floreria").error(f"WhatsApp modificación: {e}")

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
    pedido.estado_florista = EF.CAMBIO_SUGERIDO
    pedido.nota_florista = nota
    await db.commit()

    if pedido.webhook_url:
        from app.routers.pedidos import _disparar_webhook
        _disparar_webhook(pedido.webhook_url, pedido.numero, pedido.estado, pedido.estado, extra={
            "accion": "florista_sugiere_cambio",
            "nota": nota,
            "telefono_cliente": await _tel_cliente(pedido, db),
        })
    elif pedido.tracking_token and pedido.customer_id:
        try:
            from app.models.clientes import Cliente
            cliente_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cliente = cliente_result.scalar_one_or_none()
            if cliente and cliente.telefono:
                tracking_url = f"https://www.florerialucy.com/catalogo/seguimiento.html?token={pedido.tracking_token}"
                msg = (
                    f"Hola {cliente.nombre.split()[0]} 🌸\n\n"
                    f"Nuestro florista tiene una sugerencia para tu pedido {pedido.numero}:\n\n"
                    f"💬 \"{nota}\"\n\n"
                    f"Revisa y responde aquí:\n{tracking_url}"
                )
                from app.routers.catalogo import _enviar_whatsapp
                await _enviar_whatsapp(cliente.telefono, msg)
        except Exception as e:
            import logging
            logging.getLogger("floreria").error(f"WhatsApp cambio sugerido: {e}")

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
    estado_anterior = pedido.estado
    pedido.estado = EP.CANCELADO
    pedido.estado_florista = EF.RECHAZADO
    pedido.nota_florista = razon
    pedido.cancelado_razon = razon or "Rechazado por florista"
    await db.commit()

    if pedido.webhook_url:
        from app.routers.pedidos import _disparar_webhook
        _disparar_webhook(pedido.webhook_url, pedido.numero, estado_anterior, EP.CANCELADO, extra={
            "accion": "florista_rechaza",
            "nota": razon,
            "telefono_cliente": await _tel_cliente(pedido, db),
        })
    elif pedido.tracking_token and pedido.customer_id:
        # Pedido web — notificar cancelación al cliente
        try:
            from app.models.clientes import Cliente
            cliente_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cliente = cliente_result.scalar_one_or_none()
            if cliente and cliente.telefono:
                msg = (
                    f"Hola {cliente.nombre.split()[0]} 🌸\n\n"
                    f"Lamentamos informarte que tu pedido {pedido.numero} no pudo ser procesado.\n\n"
                    f"Motivo: {razon or 'No disponible'}\n\n"
                    f"Si deseas, puedes hacer un nuevo pedido en nuestro catálogo:\nhttps://www.florerialucy.com/catalogo/"
                )
                from app.routers.catalogo import _enviar_whatsapp
                await _enviar_whatsapp(cliente.telefono, msg)
        except Exception as e:
            import logging
            logging.getLogger("floreria").error(f"WhatsApp cancelación web: {e}")

    return {"ok": True, "id": pedido.id, "estado": pedido.estado}


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
    pedido.estado = EP.CANCELADO
    pedido.cancelado_razon = razon
    await db.commit()
    return {"ok": True, "id": pedido.id, "estado": pedido.estado}


@router.get("/pedidos/{pedido_id}/etiqueta-data")
async def etiqueta_data(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Datos mínimos para imprimir etiquetas 2x1."""
    _auth(panel_session)
    pedido = await _get_pedido(pedido_id, db)
    result = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == pedido.id))
    items_db = result.scalars().all()
    items = []
    for item in items_db:
        prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
        prod = prod_result.scalar_one_or_none()
        nombre = item.nombre_personalizado if item.es_personalizado and item.nombre_personalizado else (prod.nombre if prod else "Producto")
        for _ in range(item.cantidad):
            items.append(nombre)
    return {
        "folio": pedido.numero,
        "receptor_nombre": pedido.receptor_nombre or "",
        "items": items,
        "total_items": len(items),
    }


@router.post("/pedidos/{pedido_id}/listo")
async def listo(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    pedido = await _get_pedido(pedido_id, db)
    pedido.estado = EP.LISTO_TALLER
    pedido.listo_at = ahora()
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
    pedido.estado = EP.ENTREGADO
    pedido.entregado_at = ahora()
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


@router.get("/etiquetas-manana-data")
async def etiquetas_manana_data(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Datos de etiquetas 2x1 para todos los pedidos de mañana."""
    _auth(panel_session)
    manana = hoy() + timedelta(days=1)
    result = await db.execute(
        select(Pedido)
        .where(Pedido.fecha_entrega == manana)
        .where(Pedido.estado.in_([EP.PAGADO, EP.EN_PRODUCCION, EP.LISTO_TALLER]))
        .order_by(Pedido.horario_entrega, Pedido.hora_exacta)
    )
    pedidos_list = result.scalars().all()
    all_etiquetas = []
    for p in pedidos_list:
        items_result = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == p.id))
        items_db = items_result.scalars().all()
        items = []
        for item in items_db:
            prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
            prod = prod_result.scalar_one_or_none()
            nombre = item.nombre_personalizado if item.es_personalizado and item.nombre_personalizado else (prod.nombre if prod else "Producto")
            for _ in range(item.cantidad):
                items.append(nombre)
        all_etiquetas.append({
            "folio": p.numero,
            "receptor_nombre": p.receptor_nombre or "",
            "items": items,
            "total_items": len(items),
        })
    return all_etiquetas


@router.post("/imprimir-etiquetas-manana")
async def imprimir_etiquetas_manana(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    manana = hoy() + timedelta(days=1)
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

def _parse_fecha(fecha_str: str | None):
    """Convierte string fecha a date, o devuelve hoy si es None."""
    if fecha_str:
        return date_type.fromisoformat(fecha_str)
    return None


@router.get("/entregas/lobby")
async def entregas_lobby(
    fecha: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    query = select(Pedido).where(Pedido.estado.in_(EP.LISTOS), Pedido.metodo_entrega == ME.MOSTRADOR)
    f = _parse_fecha(fecha)
    if f:
        query = query.where(Pedido.fecha_entrega == f)
    result = await db.execute(query.order_by(Pedido.listo_at))
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/entregas/por-recoger")
async def entregas_por_recoger(
    fecha: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    query = select(Pedido).where(Pedido.estado.in_(EP.LISTOS), Pedido.metodo_entrega.in_(ME.PARA_RECOGER))
    f = _parse_fecha(fecha)
    if f:
        query = query.where(Pedido.fecha_entrega == f)
    result = await db.execute(query.order_by(Pedido.fecha_entrega, Pedido.horario_entrega))
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/entregas/envios")
async def entregas_envios(
    fecha: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    query = select(Pedido).where(Pedido.estado.in_(EP.LISTOS + [EP.EN_CAMINO]), Pedido.metodo_entrega.in_(ME.PARA_ENVIO))
    f = _parse_fecha(fecha)
    if f:
        query = query.where(Pedido.fecha_entrega == f)
    result = await db.execute(query.order_by(Pedido.fecha_entrega, Pedido.horario_entrega))
    pedidos = result.scalars().all()
    return [await _serializar_pedido_taller(p, db) for p in pedidos]


@router.get("/entregas/resumen-dia")
async def entregas_resumen_dia(
    fecha: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    fecha_hoy = _parse_fecha(fecha) or hoy()

    r_total = await db.execute(
        select(func.count(Pedido.id)).where(Pedido.fecha_entrega == fecha_hoy)
    )
    total = r_total.scalar() or 0

    r_entregados = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.fecha_entrega == fecha_hoy,
            Pedido.estado.in_([EP.ENTREGADO]),
        )
    )
    entregados = r_entregados.scalar() or 0

    r_pendientes = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.fecha_entrega == fecha_hoy,
            Pedido.estado.notin_([EP.ENTREGADO, EP.CANCELADO]),
        )
    )
    pendientes = r_pendientes.scalar() or 0

    r_repartidores = await db.execute(
        select(func.count(func.distinct(Pedido.ruta))).where(
            Pedido.fecha_entrega == fecha_hoy,
            Pedido.estado == EP.EN_CAMINO,
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
    ts_ahora = ahora()

    # Mark all pedidos in this batch as Listo
    result = await db.execute(
        select(Pedido).where(
            Pedido.modo_fecha_fuerte_lote == lote,
            Pedido.estado.in_(EP.EN_TALLER_PRODUCCION),
        )
    )
    pedidos = result.scalars().all()
    if not pedidos:
        raise HTTPException(status_code=404, detail=f"No se encontraron pedidos en lote '{lote}'")

    ids = []
    for p in pedidos:
        p.estado = EP.LISTO
        p.listo_at = ts_ahora
        ids.append(p.id)

    await db.commit()
    return {"ok": True, "lote": lote, "pedidos_actualizados": ids}
