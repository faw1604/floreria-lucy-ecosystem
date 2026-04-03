from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import httpx
import os
import logging

logger = logging.getLogger("floreria")
from app.database import get_db
from app.models.productos import Producto
from app.models.clientes import Cliente
from app.models.pedidos import Pedido, ItemPedido
from app.models.pagos import MetodoPago
from app.models.funerarias import Funeraria
from app.models.configuracion import ConfiguracionNegocio
from app.core.config import TZ
from app.core.utils import ahora, hoy, generar_folio
from app.core.estados import EstadoPedido as EP, EstadoFlorista as EF, MetodoEntrega as ME
from app.routers.auth import verificar_sesion

router = APIRouter()


async def _generar_folio(db: AsyncSession) -> str:
    return await generar_folio(db)


@router.get("/productos")
async def pos_productos(
    q: str = "",
    categoria: str = "",
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    query = select(Producto).where(Producto.activo == True)
    if q:
        query = query.where(Producto.nombre.ilike(f"%{q}%"))
    if categoria:
        query = query.where(Producto.categoria == categoria)
    query = query.order_by(Producto.categoria, Producto.nombre)
    result = await db.execute(query)
    prods = result.scalars().all()
    return [{
        "id": p.id, "codigo": p.codigo, "nombre": p.nombre, "categoria": p.categoria,
        "precio": p.precio, "precio_descuento": p.precio_descuento,
        "imagen_url": p.imagen_url, "disponible_hoy": p.disponible_hoy,
    } for p in prods]


@router.get("/productos/categorias")
async def pos_categorias(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(Producto.categoria, func.count(Producto.id))
        .where(Producto.activo == True, Producto.imagen_url.isnot(None))
        .group_by(Producto.categoria)
        .order_by(Producto.categoria)
    )
    return [{"categoria": r[0], "count": r[1]} for r in result.all()]


@router.get("/clientes/buscar")
async def pos_buscar_cliente(
    q: str = "",
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    if len(q) < 2:
        return []
    query = select(Cliente).where(
        (Cliente.nombre.ilike(f"%{q}%")) | (Cliente.telefono.ilike(f"%{q}%")) | (Cliente.codigo_referido.ilike(f"%{q}%"))
    ).limit(15)
    result = await db.execute(query)
    clientes = result.scalars().all()
    # Check primera compra for each
    out = []
    for c in clientes:
        pedidos_r = await db.execute(
            select(func.count(Pedido.id)).where(Pedido.customer_id == c.id, Pedido.estado != "pendiente_pago")
        )
        tiene_pedidos = pedidos_r.scalar() > 0
        out.append({
            "id": c.id, "nombre": c.nombre, "telefono": c.telefono,
            "email": c.email, "primera_compra": not tiene_pedidos,
        })
    return out


@router.post("/cliente")
async def pos_crear_cliente(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    telefono = "".join(c for c in data.get("telefono", "") if c.isdigit())
    if len(telefono) > 10 and telefono.startswith("52"):
        telefono = telefono[2:]
    # Check duplicate
    existing = await db.execute(select(Cliente).where(Cliente.telefono == telefono))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ya existe un cliente con ese teléfono")
    from app.core.security import generar_codigo_referido
    cliente = Cliente(
        nombre=data.get("nombre", ""),
        telefono=telefono,
        email=data.get("email"),
        direccion_default=data.get("direccion"),
        fuente="Mostrador",
        codigo_referido=generar_codigo_referido(data.get("nombre", ""), telefono),
    )
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return {"id": cliente.id, "nombre": cliente.nombre, "telefono": cliente.telefono}


@router.post("/geocodificar")
async def pos_geocodificar(
    request: Request,
    panel_session: str | None = Cookie(default=None),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    direccion = data.get("direccion", "")
    if not direccion:
        return {"error": "Dirección vacía"}

    from app.services.rutas import obtener_ruta
    ua = "FloreriaLucy/1.0 florerialucychihuahua@gmail.com"
    calle = direccion.split(",")[0].strip()

    async def geocode(params):
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params=params, headers={"User-Agent": ua}, timeout=10,
            )
            return r.json()

    try:
        data = await geocode({
            "street": calle, "city": "Chihuahua", "state": "Chihuahua", "country": "Mexico",
            "countrycodes": "mx", "bounded": "1", "viewbox": "-106.25,28.83,-105.92,28.55",
            "format": "json", "limit": "1",
        })
        if not data:
            data = await geocode({
                "q": f"{direccion}, Chihuahua, Mexico",
                "countrycodes": "mx", "bounded": "1", "viewbox": "-106.25,28.83,-105.92,28.55",
                "format": "json", "limit": "1",
            })
    except Exception:
        return {"error": "Error al conectar con el geocodificador"}

    if not data:
        return {"error": "No se pudo geocodificar la dirección"}

    lat = float(data[0]["lat"])
    lng = float(data[0]["lon"])
    ruta = obtener_ruta(lat, lng)
    from app.services.zonas_envio import obtener_zona_envio
    zona = obtener_zona_envio(lat, lng)
    return {
        "lat": lat, "lng": lng, "ruta": ruta,
        "zona_envio": zona["zona"] if zona else None,
        "tarifa_envio": zona["tarifa"] * 100 if zona else None,
        "display_name": data[0].get("display_name", ""),
    }


@router.post("/pedido")
async def pos_crear_pedido(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    import traceback as _tb
    try:
        return await _pos_crear_pedido_inner(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[POS PEDIDO] Error: {e}\n{_tb.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def _pos_crear_pedido_inner(request, db):
    data = await request.json()
    tipo = data.get("tipo", "mostrador")
    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="No hay productos en el pedido")

    # Validate funeral products (skip custom items)
    if tipo == "funeral":
        for item in items:
            if item.get("es_personalizado") or not item.get("producto_id"):
                continue
            prod = (await db.execute(select(Producto).where(Producto.id == item["producto_id"]))).scalar_one_or_none()
            if prod and prod.categoria.lower() != "funeral":
                raise HTTPException(status_code=400, detail=f"Producto '{prod.nombre}' no es de categoría funeral")

    # Calculate subtotal
    subtotal = sum(it["precio_unitario"] * it["cantidad"] for it in items)

    # Tax — calculate IVA only on non-chocolate products
    tipo_impuesto = data.get("tipo_impuesto", "NA")
    impuesto = 0
    if tipo_impuesto == "IVA":
        # Split subtotal by category: chocolates get IEPS (desglosado), rest gets IVA
        sub_flores = 0
        for it in items:
            prod = (await db.execute(select(Producto).where(Producto.id == it.get("producto_id")))).scalar_one_or_none()
            cat = (prod.categoria if prod else "").lower()
            monto_item = it["precio_unitario"] * it["cantidad"]
            if "chocolates gourmet" not in cat:
                sub_flores += monto_item
        impuesto = int(sub_flores * 0.16)

    # Shipping — dynamic tariffs from config
    envio = 0
    zona = data.get("zona_envio")
    if tipo == "domicilio" and zona:
        cfg_result = await db.execute(select(ConfiguracionNegocio))
        cfg_map = {c.clave: c.valor for c in cfg_result.scalars().all()}
        if cfg_map.get("temporada_modo") == "alta":
            envio = int(cfg_map.get("temporada_envio_unico", "9900"))
        else:
            tarifas = {
                "Morada": int(cfg_map.get("zona_tarifa_morada", "9900")),
                "Azul": int(cfg_map.get("zona_tarifa_azul", "15900")),
                "Verde": int(cfg_map.get("zona_tarifa_verde", "19900")),
            }
            envio = tarifas.get(zona, 0)

    # Discounts from frontend
    descuento = data.get("descuento_total", 0)
    cliente_id = data.get("cliente_id")

    # Link de pago commission
    comision = 0
    pagos = data.get("pagos", [])
    for pago in pagos:
        nombre_pago = (pago.get("nombre") or "").lower()
        if pago.get("metodo_pago_id"):
            mp = (await db.execute(select(MetodoPago).where(MetodoPago.id == pago["metodo_pago_id"]))).scalar_one_or_none()
            if mp and "link" in (mp.tipo or "").lower():
                comision = int(pago["monto"] * 0.04)
        elif "link" in nombre_pago:
            comision = int(pago["monto"] * 0.04)

    # Cargo hora especifica
    cargo_hora = data.get("cargo_hora_especifica", 0)
    total = subtotal + impuesto + envio - descuento + comision + cargo_hora

    # Validate payment
    estado_pedido = data.get("estado", "pendiente_pago")
    if estado_pedido == "pagado":
        suma_pagos = sum(p["monto"] for p in pagos)
        if suma_pagos < total:
            raise HTTPException(status_code=400, detail=f"Falta asignar ${(total - suma_pagos) / 100:.0f}")

    # Build notas for funeral
    notas = data.get("notas_entrega", "")
    if tipo == "funeral":
        funeral_parts = []
        if data.get("funeraria_id"):
            fun = (await db.execute(select(Funeraria).where(Funeraria.id == data["funeraria_id"]))).scalar_one_or_none()
            if fun:
                funeral_parts.append(f"FUNERAL — {fun.nombre}")
                zona = fun.zona
                envio = fun.costo_envio
        if data.get("nombre_fallecido"):
            funeral_parts.append(f"Fallecido: {data['nombre_fallecido']}")
        if data.get("sala"):
            funeral_parts.append(f"Sala: {data['sala']}")
        if data.get("banda"):
            funeral_parts.append(f"Banda: {data['banda']}")
        if data.get("horario_velacion"):
            funeral_parts.append(f"Velacion: {data['horario_velacion']}")
        if funeral_parts:
            notas = ". ".join(funeral_parts) + (f". {notas}" if notas else "")
        # Recalc total with funeral shipping
        total = subtotal + impuesto + envio - descuento + comision + cargo_hora

    folio = await _generar_folio(db)
    horario = data.get("horario_entrega")
    if horario == "hora_especifica":
        horario = None

    from datetime import date as date_type
    fecha_str = data.get("fecha_entrega")
    fecha_entrega = date_type.fromisoformat(fecha_str) if fecha_str else datetime.now(TZ).date()

    # Determinar metodo_entrega y estado correcto
    es_mostrador = tipo == "mostrador" or (not data.get("direccion_entrega") and not zona and tipo not in ("envio", "funeral", "recoger", "domicilio"))
    es_funeral = tipo == "funeral"
    if es_mostrador:
        _metodo = ME.MOSTRADOR
    elif tipo == "recoger":
        _metodo = ME.RECOGER
    elif es_funeral and (data.get("direccion_entrega") or data.get("funeraria_id")):
        _metodo = ME.FUNERAL_ENVIO
    elif es_funeral:
        _metodo = ME.FUNERAL_RECOGER
    else:
        _metodo = ME.ENVIO

    # Determinar si es solo reservas (ya elaboradas) o necesita producción
    reserva_ids = data.get("reserva_ids", [])
    solo_reservas = len(reserva_ids) > 0 and len(reserva_ids) >= len(items)

    # Pagado + solo reservas en mostrador → Listo (se lo lleva ya hecho)
    # Pagado + cualquier otra cosa → En producción (florista debe elaborar)
    if estado_pedido == "pagado":
        if es_mostrador and solo_reservas:
            _estado = EP.LISTO
            _estado_fl = EF.APROBADO
        else:
            _estado = EP.EN_PRODUCCION
            _estado_fl = EF.APROBADO
    else:
        _estado = EP.PENDIENTE_PAGO
        _estado_fl = EF.PENDIENTE_PAGO

    pedido = Pedido(
        numero=folio,
        customer_id=cliente_id,
        canal="Mostrador",
        estado=_estado,
        estado_florista=_estado_fl,
        metodo_entrega=_metodo,
        produccion_at=ahora() if _estado == "En producción" else None,
        fecha_entrega=fecha_entrega,
        horario_entrega=horario,
        hora_exacta=data.get("hora_especifica"),
        zona_entrega=zona,
        direccion_entrega=data.get("direccion_entrega"),
        receptor_nombre=data.get("nombre_destinatario"),
        receptor_telefono=data.get("telefono_destinatario"),
        dedicatoria=data.get("dedicatoria"),
        notas_internas=notas or None,
        forma_pago=", ".join([p.get("nombre") or str(p.get("metodo_pago_id", "")) for p in pagos]) if pagos else "Efectivo",
        pago_confirmado=estado_pedido == "pagado",
        pago_confirmado_at=ahora() if estado_pedido == "pagado" else None,
        subtotal=subtotal,
        envio=envio,
        total=total,
        tipo_especial="Funeral" if tipo == "funeral" else None,
        ruta=data.get("ruta"),
        requiere_factura=data.get("requiere_factura", False),
    )
    db.add(pedido)
    await db.flush()

    for it in items:
        db.add(ItemPedido(
            pedido_id=pedido.id,
            producto_id=it.get("producto_id") or 0,
            cantidad=it["cantidad"],
            precio_unitario=it["precio_unitario"],
            es_personalizado=it.get("es_personalizado", False),
            nombre_personalizado=it.get("nombre_personalizado"),
            observaciones=it.get("observaciones"),
        ))

    # Save datos fiscales if factura
    _dfd = data.get("datos_fiscales")
    if _dfd and data.get("requiere_factura"):
        from app.models.fiscales import DatosFiscalesCliente
        _ndf = DatosFiscalesCliente(
            cliente_id=cliente_id, rfc=_dfd.get("rfc"), razon_social=_dfd.get("razon_social"),
            regimen_fiscal=_dfd.get("regimen_fiscal"), uso_cfdi=_dfd.get("uso_cfdi"),
            correo_fiscal=_dfd.get("correo_fiscal"), codigo_postal=_dfd.get("codigo_postal"))
        db.add(_ndf)
        await db.flush()
        pedido.datos_fiscales_id = _ndf.id

    await db.commit()
    await db.refresh(pedido)

    # Marcar reservas como vendidas
    reserva_ids = data.get("reserva_ids", [])
    if reserva_ids:
        from app.models.reservas import Reserva
        for rid in reserva_ids:
            r_res = await db.execute(
                select(Reserva).where(Reserva.id == rid, Reserva.estado == "disponible")
            )
            reserva = r_res.scalar_one_or_none()
            if reserva:
                reserva.estado = "vendida"
                reserva.pedido_id = pedido.id
                reserva.vendida_at = ahora()
        await db.commit()

    return {
        "ok": True, "folio": pedido.numero, "id": pedido.id,
        "total": total, "subtotal": subtotal, "impuesto": impuesto,
        "envio": envio, "descuento": descuento, "comision": comision,
        "estado": pedido.estado,
    }


async def _serializar_pedido_pos(p, db):
    items_r = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == p.id))
    items = []
    for it in items_r.scalars().all():
        if it.es_personalizado and it.nombre_personalizado:
            nombre = f"⚡ {it.nombre_personalizado}"
        else:
            prod = (await db.execute(select(Producto).where(Producto.id == it.producto_id))).scalar_one_or_none()
            nombre = prod.nombre if prod else "?"
        items.append({"nombre": nombre, "cantidad": it.cantidad, "precio_unitario": it.precio_unitario})
    cliente_nombre = None
    cliente_telefono = None
    if p.customer_id:
        cli = (await db.execute(select(Cliente).where(Cliente.id == p.customer_id))).scalar_one_or_none()
        if cli:
            cliente_nombre = cli.nombre
            cliente_telefono = cli.telefono
    return {
        "id": p.id, "folio": p.numero, "estado": p.estado, "canal": p.canal,
        "cliente_nombre": cliente_nombre, "cliente_telefono": cliente_telefono, "customer_id": p.customer_id,
        "items": items, "subtotal": p.subtotal, "envio": p.envio, "total": p.total,
        "forma_pago": p.forma_pago, "pago_confirmado": p.pago_confirmado,
        "tipo_especial": p.tipo_especial, "horario_entrega": p.horario_entrega,
        "hora_exacta": p.hora_exacta, "zona_entrega": p.zona_entrega,
        "direccion_entrega": p.direccion_entrega, "receptor_nombre": p.receptor_nombre,
        "receptor_telefono": p.receptor_telefono, "dedicatoria": p.dedicatoria,
        "notas_internas": p.notas_internas, "ruta": p.ruta,
        "metodo_entrega": p.metodo_entrega,
        "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None,
        "comprobante_pago_url": p.comprobante_pago_url,
        "requiere_factura": p.requiere_factura,
        "pago_confirmado_at": p.pago_confirmado_at.isoformat() if p.pago_confirmado_at else None,
    }


@router.get("/pedidos-hoy")
async def pos_pedidos_hoy(
    periodo: str = "hoy",
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    metodo_pago: str | None = None,
    estado: str | None = None,
    canal: str | None = None,
    tipo: str | None = None,
    cliente_id: int | None = None,
    filtrar_por: str = "fecha_pedido",  # fecha_pedido | fecha_entrega
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    from datetime import date as date_type, time as time_type
    from calendar import monthrange
    ts_ahora = datetime.now(TZ)
    hoy = ts_ahora.date()

    # Week: Sunday=0..Saturday=6 (Mexican convention)
    dow = (hoy.weekday() + 1) % 7  # convert Mon=0 to Sun=0

    # Determine date range (local dates)
    skip_date_filter = False
    if periodo == "todos":
        skip_date_filter = True
        f_ini = f_fin = hoy  # unused but avoids unbound
    elif periodo == "rango" and fecha_inicio and fecha_fin:
        f_ini = date_type.fromisoformat(fecha_inicio)
        f_fin = date_type.fromisoformat(fecha_fin)
    elif periodo == "ayer":
        f_ini = f_fin = hoy - timedelta(days=1)
    elif periodo == "semana":
        f_ini = hoy - timedelta(days=dow)  # Sunday of this week
        f_fin = f_ini + timedelta(days=6)  # Saturday
        if f_fin > hoy:
            f_fin = hoy
    elif periodo == "semana_pasada":
        inicio_esta = hoy - timedelta(days=dow)
        f_ini = inicio_esta - timedelta(days=7)
        f_fin = inicio_esta - timedelta(days=1)
    elif periodo == "mes":
        f_ini = hoy.replace(day=1)
        f_fin = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])
        if f_fin > hoy:
            f_fin = hoy
    elif periodo == "mes_pasado":
        primer_dia_este_mes = hoy.replace(day=1)
        ultimo_dia_mes_pasado = primer_dia_este_mes - timedelta(days=1)
        f_ini = ultimo_dia_mes_pasado.replace(day=1)
        f_fin = ultimo_dia_mes_pasado
    else:  # hoy
        f_ini = f_fin = hoy

    # Build query with date filter
    if skip_date_filter:
        query = select(Pedido).order_by(Pedido.fecha_pedido.desc())
    elif filtrar_por == "fecha_entrega":
        # Filtrar por fecha_entrega (date local, sin timezone) — para finanzas
        query = select(Pedido).where(
            Pedido.fecha_entrega >= f_ini,
            Pedido.fecha_entrega <= f_fin,
        ).order_by(Pedido.fecha_pedido.desc())
    else:
        # Filtrar por fecha_pedido (datetime UTC) — para transacciones POS
        utc_start = datetime.combine(f_ini, time_type.min).replace(tzinfo=TZ).astimezone().replace(tzinfo=None)
        utc_end = datetime.combine(f_fin, time_type.max).replace(tzinfo=TZ).astimezone().replace(tzinfo=None)
        query = select(Pedido).where(
            Pedido.fecha_pedido >= utc_start,
            Pedido.fecha_pedido <= utc_end,
        ).order_by(Pedido.fecha_pedido.desc())

    # Filter by cliente_id
    if cliente_id:
        query = query.where(Pedido.customer_id == cliente_id)

    # Filter by canal
    if canal:
        canales = [c.strip() for c in canal.split(",")]
        canal_map = {"POS": "Mostrador", "WhatsApp": "WhatsApp", "Web": "Web"}
        db_canales = [canal_map.get(c, c) for c in canales]
        query = query.where(Pedido.canal.in_(db_canales))

    # Filter by estado
    estado_filter = None
    if estado:
        estado_filter = [e.strip() for e in estado.split(",")]

    # Filter by tipo
    from sqlalchemy import or_, and_
    if tipo:
        tipos = [t.strip() for t in tipo.split(",")]
        tipo_conditions = []
        for t in tipos:
            if t == "Funeral":
                tipo_conditions.append(Pedido.tipo_especial == "Funeral")
            elif t == "Mostrador":
                tipo_conditions.append(and_(Pedido.tipo_especial.is_(None), Pedido.direccion_entrega.is_(None)))
            elif t == "Domicilio":
                tipo_conditions.append(and_(Pedido.tipo_especial.is_(None), Pedido.direccion_entrega.isnot(None)))
            elif t == "Recoger":
                tipo_conditions.append(Pedido.tipo_especial == "Recoger")
        if tipo_conditions:
            query = query.where(or_(*tipo_conditions))

    # Filter by metodo_pago
    if metodo_pago:
        metodos = [m.strip() for m in metodo_pago.split(",")]
        mp_conds = [Pedido.forma_pago.ilike(f"%{m}%") for m in metodos]
        query = query.where(or_(*mp_conds))

    result = await db.execute(query)
    pedidos = result.scalars().all()

    pendientes = []
    finalizados = []
    total_vendido = 0
    desglose_pago = {}

    # Map estado filter values to DB values
    estado_map = {
        "pendiente_pago": [EP.PENDIENTE_PAGO, "pendiente_pago", EP.COMPROBANTE_RECIBIDO, EP.ESPERANDO_VALIDACION],
        "pagado": [EP.LISTO, EP.PAGADO],
        "Listo": [EP.LISTO],
        "listo_taller": [EP.LISTO_TALLER, "Listo taller"],
        "En producción": [EP.EN_PRODUCCION],
        "en_camino": [EP.EN_CAMINO],
        "entregado": [EP.ENTREGADO],
        "cancelado": [EP.CANCELADO],
    }

    for p in pedidos:
        # Apply estado filter
        if estado_filter:
            matched = False
            for ef in estado_filter:
                if p.estado in estado_map.get(ef, [ef]):
                    matched = True
                    break
            if not matched:
                continue

        data = await _serializar_pedido_pos(p, db)
        # Convert UTC to Chihuahua for display
        if p.fecha_pedido:
            from zoneinfo import ZoneInfo
            utc_dt = p.fecha_pedido.replace(tzinfo=ZoneInfo("UTC"))
            chih_dt = utc_dt.astimezone(TZ)
            data["fecha_pedido"] = chih_dt.strftime("%Y-%m-%d %H:%M")
        else:
            data["fecha_pedido"] = None
        if p.estado in ("Pendiente pago", "pendiente_pago", "comprobante_recibido", "esperando_validacion"):
            pendientes.append(data)
        else:
            finalizados.append(data)
            # No sumar cancelados ni rechazados al total de ventas
            if p.estado not in (EP.CANCELADO, "Cancelado", "rechazado"):
                total_vendido += p.total or 0
                for metodo in (p.forma_pago or "").split(", "):
                    metodo = metodo.strip()
                    if metodo:
                        desglose_pago[metodo] = desglose_pago.get(metodo, 0) + (p.total or 0)

    # Ordenar finalizados por fecha de pago (más reciente primero)
    finalizados.sort(key=lambda x: x.get("pago_confirmado_at") or "", reverse=True)

    return {
        "pendientes": pendientes,
        "finalizados": finalizados,
        "resumen": {
            "total_vendido": total_vendido,
            "desglose_pago": desglose_pago,
            "num_finalizados": len(finalizados),
            "num_pendientes": len(pendientes),
        },
    }


@router.patch("/pedido/{pedido_id}/cambiar-estado")
async def pos_cambiar_estado(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Cambiar estado de un pedido desde POS. No envía notificaciones."""
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    nuevo_estado = data.get("estado")
    if not nuevo_estado:
        raise HTTPException(status_code=400, detail="Falta el campo 'estado'")
    from app.core.estados import EstadoPedido as EP
    estados_validos = [
        EP.ESPERANDO_VALIDACION, EP.PENDIENTE_PAGO, EP.COMPROBANTE_RECIBIDO,
        EP.PAGADO, EP.EN_PRODUCCION, EP.LISTO, EP.LISTO_TALLER,
        EP.EN_CAMINO, EP.ENTREGADO, EP.CANCELADO, EP.INTENTO_FALLIDO,
    ]
    if nuevo_estado not in estados_validos:
        raise HTTPException(status_code=400, detail=f"Estado no válido: {nuevo_estado}")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    estado_anterior = pedido.estado
    pedido.estado = nuevo_estado
    if nuevo_estado == EP.ENTREGADO:
        from app.core.utils import ahora
        pedido.entregado_at = ahora()
    await db.commit()
    return {"ok": True, "folio": pedido.numero, "estado_anterior": estado_anterior, "estado_nuevo": nuevo_estado}


@router.patch("/pedido/{pedido_id}/finalizar")
async def pos_finalizar_pedido(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    import traceback as _tb
    try:
        return await _pos_finalizar_inner(pedido_id, request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[POS FINALIZAR] Error: {e}\n{_tb.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def _pos_finalizar_inner(pedido_id, request, db):
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    data = await request.json()
    pagos = data.get("pagos", [])
    suma_pagos = sum(p["monto"] for p in pagos)
    if suma_pagos < (pedido.total or 0):
        raise HTTPException(status_code=400, detail=f"Falta asignar ${((pedido.total or 0) - suma_pagos) / 100:.0f}")

    # Determinar si es mostrador con solo reservas o necesita producción
    m = pedido.metodo_entrega or ""
    if m == ME.MOSTRADOR:
        pedido.estado = EP.LISTO
    else:
        pedido.estado = EP.EN_PRODUCCION
        pedido.produccion_at = ahora()
    pedido.estado_florista = EF.APROBADO
    pedido.pago_confirmado = True
    pedido.pago_confirmado_at = ahora()
    pedido.forma_pago = ", ".join(p.get("nombre", "") for p in pagos if p.get("nombre"))
    await db.commit()

    # WhatsApp al cliente web: pago confirmado
    if pedido.canal == "Web" and pedido.tracking_token and pedido.customer_id:
        try:
            cliente_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cliente = cliente_result.scalar_one_or_none()
            if cliente and cliente.telefono:
                tracking_url = f"https://www.florerialucy.com/catalogo/seguimiento.html?token={pedido.tracking_token}"
                from app.routers.catalogo import _enviar_whatsapp
                await _enviar_whatsapp(cliente.telefono,
                    f"Hola {cliente.nombre.split()[0]} 🌸\n\n"
                    f"Tu pago para el pedido {pedido.numero} fue confirmado! Tu arreglo sera elaborado pronto.\n\n"
                    f"Sigue el estatus aqui:\n{tracking_url}"
                )
        except Exception:
            pass

    return {"ok": True, "folio": pedido.numero, "estado": pedido.estado}


@router.patch("/pedido/{pedido_id}/editar-fecha")
async def pos_editar_fecha(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    data = await request.json()
    from datetime import date as date_type
    fecha_str = data.get("fecha_entrega")
    if fecha_str:
        pedido.fecha_entrega = date_type.fromisoformat(fecha_str)
    if "horario_entrega" in data:
        pedido.horario_entrega = data["horario_entrega"]
    if "hora_especifica" in data:
        pedido.hora_exacta = data["hora_especifica"]
    await db.commit()
    return {"ok": True, "folio": pedido.numero}


@router.patch("/pedido/{pedido_id}/editar")
async def pos_editar_pedido(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    data = await request.json()
    campos_editables = [
        "receptor_nombre", "receptor_telefono", "direccion_entrega",
        "dedicatoria", "notas_internas", "horario_entrega", "hora_exacta",
        "fecha_entrega",
    ]
    for campo in campos_editables:
        if campo in data:
            setattr(pedido, campo, data[campo])
    await db.commit()
    return {"ok": True, "folio": pedido.numero}


@router.patch("/pedido/{pedido_id}/completar")
async def pos_completar_pedido(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    data = await request.json()
    estado_pedido = data.get("estado", "pendiente_pago")
    items = data.get("items", [])
    pagos = data.get("pagos", [])

    # Recalculate totals
    subtotal = sum(it["precio_unitario"] * it["cantidad"] for it in items)
    tipo_impuesto = data.get("tipo_impuesto", "NA")
    impuesto = 0
    if tipo_impuesto == "IVA":
        sub_flores = 0
        for it in items:
            prod = (await db.execute(select(Producto).where(Producto.id == it.get("producto_id")))).scalar_one_or_none()
            cat = (prod.categoria if prod else "").lower()
            if "chocolates gourmet" not in cat:
                sub_flores += it["precio_unitario"] * it["cantidad"]
        impuesto = int(sub_flores * 0.16)
    descuento = data.get("descuento_total", 0)
    cargo_hora = data.get("cargo_hora_especifica", 0)
    comision = 0
    for pago in pagos:
        if "link" in (pago.get("nombre") or "").lower():
            comision = int(pago["monto"] * 0.04)

    tipo = data.get("tipo", "mostrador")
    envio = 0
    zona = data.get("zona_envio")
    if tipo == "domicilio" and zona:
        cfg_result = await db.execute(select(ConfiguracionNegocio))
        cfg_map = {c.clave: c.valor for c in cfg_result.scalars().all()}
        if cfg_map.get("temporada_modo") == "alta":
            envio = int(cfg_map.get("temporada_envio_unico", "9900"))
        else:
            tarifas = {
                "Morada": int(cfg_map.get("zona_tarifa_morada", "9900")),
                "Azul": int(cfg_map.get("zona_tarifa_azul", "15900")),
                "Verde": int(cfg_map.get("zona_tarifa_verde", "19900")),
            }
            envio = tarifas.get(zona, 0)
    if tipo == "funeral" and data.get("funeraria_id"):
        fun = (await db.execute(select(Funeraria).where(Funeraria.id == data["funeraria_id"]))).scalar_one_or_none()
        if fun:
            envio = fun.costo_envio

    total = subtotal + impuesto + envio - descuento + comision + cargo_hora

    # Validate payment if finalizing
    if estado_pedido == "pagado":
        suma_pagos = sum(p["monto"] for p in pagos)
        if suma_pagos < total:
            raise HTTPException(status_code=400, detail=f"Falta asignar ${(total - suma_pagos) / 100:.0f}")

    # Determinar metodo_entrega
    es_mostrador = tipo == "mostrador" or (not data.get("direccion_entrega") and not zona and tipo not in ("envio", "funeral", "recoger", "domicilio"))
    if es_mostrador:
        _metodo = ME.MOSTRADOR
    elif tipo == "recoger":
        _metodo = ME.RECOGER
    elif tipo == "funeral" and data.get("direccion_entrega"):
        _metodo = ME.FUNERAL_ENVIO
    elif tipo == "funeral":
        _metodo = ME.FUNERAL_RECOGER
    else:
        _metodo = ME.ENVIO

    # Solo reservas en mostrador → Listo | Cualquier otro → En producción
    reserva_ids = data.get("reserva_ids", [])
    solo_reservas = len(reserva_ids) > 0 and len(reserva_ids) >= len(items)
    if estado_pedido == "pagado":
        if es_mostrador and solo_reservas:
            pedido.estado = EP.LISTO
        else:
            pedido.estado = EP.EN_PRODUCCION
            pedido.produccion_at = ahora()
        pedido.estado_florista = EF.APROBADO
    else:
        pedido.estado = EP.PENDIENTE_PAGO
        pedido.estado_florista = EF.PENDIENTE_PAGO

    pedido.metodo_entrega = _metodo
    pedido.pago_confirmado = estado_pedido == "pagado"
    if estado_pedido == "pagado" and not pedido.pago_confirmado_at:
        pedido.pago_confirmado_at = ahora()
    pedido.subtotal = subtotal
    pedido.envio = envio
    pedido.total = total
    pedido.forma_pago = ", ".join([p.get("nombre") or "" for p in pagos]) if pagos else pedido.forma_pago
    pedido.customer_id = data.get("cliente_id") or pedido.customer_id
    pedido.tipo_especial = "Funeral" if tipo == "funeral" else None
    pedido.direccion_entrega = data.get("direccion_entrega") or pedido.direccion_entrega
    pedido.receptor_nombre = data.get("nombre_destinatario") or pedido.receptor_nombre
    pedido.receptor_telefono = data.get("telefono_destinatario") or pedido.receptor_telefono
    pedido.dedicatoria = data.get("dedicatoria") or pedido.dedicatoria
    pedido.notas_internas = data.get("notas_entrega") or pedido.notas_internas
    pedido.ruta = data.get("ruta") or pedido.ruta
    if "requiere_factura" in data:
        pedido.requiere_factura = data["requiere_factura"]

    horario = data.get("horario_entrega")
    if horario == "hora_especifica":
        pedido.hora_exacta = data.get("hora_especifica")
        pedido.horario_entrega = None
    elif horario:
        pedido.horario_entrega = horario

    from datetime import date as date_type
    fecha_str = data.get("fecha_entrega")
    if fecha_str:
        pedido.fecha_entrega = date_type.fromisoformat(fecha_str)

    zona_entrega = data.get("zona_envio") or zona
    if zona_entrega:
        pedido.zona_entrega = zona_entrega

    # Replace items
    old_items = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == pedido.id))
    for oi in old_items.scalars().all():
        await db.delete(oi)

    for it in items:
        db.add(ItemPedido(
            pedido_id=pedido.id,
            producto_id=it.get("producto_id") or 0,
            cantidad=it["cantidad"],
            precio_unitario=it["precio_unitario"],
            es_personalizado=it.get("es_personalizado", False),
            nombre_personalizado=it.get("nombre_personalizado"),
            observaciones=it.get("observaciones"),
        ))

    await db.commit()
    await db.refresh(pedido)

    # Marcar reservas como vendidas
    reserva_ids = data.get("reserva_ids", [])
    if reserva_ids:
        from app.models.reservas import Reserva
        for rid in reserva_ids:
            r_res = await db.execute(
                select(Reserva).where(Reserva.id == rid, Reserva.estado == "disponible")
            )
            reserva_obj = r_res.scalar_one_or_none()
            if reserva_obj:
                reserva_obj.estado = "vendida"
                reserva_obj.pedido_id = pedido.id
                reserva_obj.vendida_at = ahora()
        await db.commit()

    return {
        "ok": True, "folio": pedido.numero, "id": pedido.id,
        "total": total, "subtotal": subtotal, "impuesto": impuesto,
        "envio": envio, "descuento": descuento, "comision": comision,
        "estado": pedido.estado,
    }


@router.get("/resumen-ventas")
async def pos_resumen_ventas(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    from datetime import time as time_type
    hoy = datetime.now(TZ).date()
    ayer = hoy - timedelta(days=1)
    dow = (hoy.weekday() + 1) % 7  # Sun=0
    inicio_semana = hoy - timedelta(days=dow)
    inicio_mes = hoy.replace(day=1)

    estados_venta = EP.VENTA_COMPLETADA

    async def contar(f_ini, f_fin):
        utc_s = datetime.combine(f_ini, time_type.min).replace(tzinfo=TZ).astimezone().replace(tzinfo=None)
        utc_e = datetime.combine(f_fin, time_type.max).replace(tzinfo=TZ).astimezone().replace(tzinfo=None)
        r = await db.execute(
            select(func.count(Pedido.id), func.coalesce(func.sum(Pedido.total), 0))
            .where(
                Pedido.fecha_pedido >= utc_s,
                Pedido.fecha_pedido <= utc_e,
                Pedido.estado.in_(estados_venta),
            )
        )
        row = r.one()
        return {"ventas": row[0], "total": round((row[1] or 0) / 100, 2)}

    return {
        "hoy": await contar(hoy, hoy),
        "ayer": await contar(ayer, ayer),
        "semana": await contar(inicio_semana, hoy),
        "mes": await contar(inicio_mes, hoy),
    }


@router.get("/corte-caja")
async def pos_corte_caja(
    periodo: str = "hoy",
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    metodo_pago: str | None = None,
    canal: str | None = None,
    tipo: str | None = None,
    cliente_id: int | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    from datetime import date as date_type, time as time_type
    from calendar import monthrange
    hoy = datetime.now(TZ).date()
    dow = (hoy.weekday() + 1) % 7

    # Date range
    skip_date_filter = False
    if periodo == "todos":
        skip_date_filter = True
        f_ini = f_fin = hoy
    elif periodo == "rango" and fecha_inicio and fecha_fin:
        f_ini = date_type.fromisoformat(fecha_inicio)
        f_fin = date_type.fromisoformat(fecha_fin)
    elif periodo == "ayer":
        f_ini = f_fin = hoy - timedelta(days=1)
    elif periodo == "semana":
        f_ini = hoy - timedelta(days=dow)
        f_fin = hoy
    elif periodo == "semana_pasada":
        inicio_esta = hoy - timedelta(days=dow)
        f_ini = inicio_esta - timedelta(days=7)
        f_fin = inicio_esta - timedelta(days=1)
    elif periodo == "mes":
        f_ini = hoy.replace(day=1)
        f_fin = hoy
    elif periodo == "mes_pasado":
        primer_dia = hoy.replace(day=1)
        ultimo_pasado = primer_dia - timedelta(days=1)
        f_ini = ultimo_pasado.replace(day=1)
        f_fin = ultimo_pasado
    else:
        f_ini = f_fin = hoy

    estados_venta = EP.VENTA_COMPLETADA

    if skip_date_filter:
        query = select(Pedido).where(Pedido.estado.in_(estados_venta))
    else:
        utc_s = datetime.combine(f_ini, time_type.min).replace(tzinfo=TZ).astimezone().replace(tzinfo=None)
        utc_e = datetime.combine(f_fin, time_type.max).replace(tzinfo=TZ).astimezone().replace(tzinfo=None)
        query = select(Pedido).where(
            Pedido.fecha_pedido >= utc_s,
            Pedido.fecha_pedido <= utc_e,
            Pedido.estado.in_(estados_venta),
        )

    if cliente_id:
        query = query.where(Pedido.customer_id == cliente_id)
    if canal:
        from sqlalchemy import or_
        canal_map = {"POS": "Mostrador", "WhatsApp": "WhatsApp", "Web": "Web"}
        db_canales = [canal_map.get(c.strip(), c.strip()) for c in canal.split(",")]
        query = query.where(Pedido.canal.in_(db_canales))
    if tipo:
        from sqlalchemy import or_, and_
        tipos = [t.strip() for t in tipo.split(",")]
        conds = []
        for t in tipos:
            if t == "Funeral": conds.append(Pedido.tipo_especial == "Funeral")
            elif t == "Mostrador": conds.append(and_(Pedido.tipo_especial.is_(None), Pedido.direccion_entrega.is_(None)))
            elif t == "Domicilio": conds.append(and_(Pedido.tipo_especial.is_(None), Pedido.direccion_entrega.isnot(None)))
            elif t == "Recoger": conds.append(Pedido.tipo_especial == "Recoger")
        if conds:
            query = query.where(or_(*conds))
    if metodo_pago:
        from sqlalchemy import or_
        metodos = [m.strip() for m in metodo_pago.split(",")]
        query = query.where(or_(*[Pedido.forma_pago.ilike(f"%{m}%") for m in metodos]))

    result = await db.execute(query)
    pedidos = result.scalars().all()

    total = 0
    por_metodo = {}
    for p in pedidos:
        total += p.total or 0
        for m in (p.forma_pago or "").split(","):
            m = m.strip()
            if m:
                por_metodo[m] = por_metodo.get(m, 0) + (p.total or 0)

    # Period label
    dias = ["DOM", "LUN", "MAR", "MIE", "JUE", "VIE", "SAB"]
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    labels = {
        "hoy": f"Hoy · {dias[hoy.weekday()]} {hoy.day} {meses[hoy.month-1]} {hoy.year}",
        "ayer": f"Ayer · {dias[(hoy - timedelta(days=1)).weekday()]} {(hoy - timedelta(days=1)).day} {meses[(hoy - timedelta(days=1)).month-1]} {(hoy - timedelta(days=1)).year}",
        "semana": "Esta semana",
        "semana_pasada": "Semana pasada",
        "mes": "Este mes",
        "mes_pasado": "Mes pasado",
        "todos": "Todos",
    }
    periodo_label = labels.get(periodo, f"{fecha_inicio} — {fecha_fin}" if fecha_inicio else periodo)

    return {
        "periodo": periodo_label,
        "total_transacciones": len(pedidos),
        "total": round(total / 100, 2),
        "por_metodo": {k: round(v / 100, 2) for k, v in por_metodo.items()},
    }


@router.get("/temporada-config")
async def pos_temporada_config(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(ConfiguracionNegocio))
    cfg = {c.clave: c.valor for c in result.scalars().all()}
    return {
        "modo": cfg.get("temporada_modo", "regular"),
        "categoria": cfg.get("temporada_categoria", ""),
        "fecha_fuerte": cfg.get("temporada_fecha_fuerte", ""),
        "dias_restriccion": int(cfg.get("temporada_dias_restriccion", "2")),
        "acepta_funerales": cfg.get("temporada_acepta_funerales", "true") == "true",
        "envio_unico": int(cfg.get("temporada_envio_unico", "9900")),
        "zona_tarifa_morada": int(cfg.get("zona_tarifa_morada", "9900")),
        "zona_tarifa_azul": int(cfg.get("zona_tarifa_azul", "15900")),
        "zona_tarifa_verde": int(cfg.get("zona_tarifa_verde", "19900")),
    }


@router.post("/verificar-clave-admin")
async def pos_verificar_clave_admin(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    clave_ingresada = data.get("clave", "")
    result = await db.execute(
        select(ConfiguracionNegocio).where(ConfiguracionNegocio.clave == "clave_admin_pos")
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=500, detail="Clave admin no configurada")
    if clave_ingresada != config.valor:
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    return {"ok": True}


@router.patch("/pedido/{pedido_id}/cancelar")
async def pos_cancelar_pedido(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    pedido.estado = "Cancelado"
    pedido.estado_florista = "cancelado"
    await db.commit()
    return {"ok": True}


@router.post("/enviar-whatsapp-cliente")
async def pos_enviar_whatsapp_cliente(
    request: Request,
    panel_session: str | None = Cookie(default=None),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    whapi_token = os.environ.get("WHAPI_TOKEN")
    if not whapi_token:
        return {"error": "WHAPI_TOKEN no configurado"}
    data = await request.json()
    telefono = "".join(c for c in data.get("telefono", "") if c.isdigit())
    if len(telefono) == 10:
        telefono = "52" + telefono
    elif len(telefono) == 13 and telefono.startswith("521"):
        telefono = "52" + telefono[3:]
    elif not telefono.startswith("52"):
        telefono = "52" + telefono
    mensaje = data.get("mensaje", "")
    if not mensaje.strip():
        return {"error": "Mensaje vacio"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://gate.whapi.cloud/messages/text",
                headers={"Authorization": f"Bearer {whapi_token}", "Content-Type": "application/json"},
                json={"to": telefono, "body": mensaje},
            )
        if r.status_code >= 400:
            return {"error": f"Whapi {r.status_code}: {r.text[:300]}"}
        return {"ok": True}
    except Exception as e:
        import traceback
        return {"error": f"Error al enviar: {type(e).__name__}: {e}", "trace": traceback.format_exc()}


@router.post("/enviar-ticket-whatsapp")
async def pos_enviar_ticket_whatsapp(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")

    whapi_token = os.environ.get("WHAPI_TOKEN")
    if not whapi_token:
        return {"error": "WHAPI_TOKEN no configurado"}

    data = await request.json()
    pedido_id = data.get("pedido_id")
    telefono = data.get("telefono", "")
    nombre = data.get("nombre_cliente", "")
    imagen_b64 = data.get("imagen_base64", "")

    # Format phone: digits only, 52XXXXXXXXXX format
    telefono = "".join(c for c in telefono if c.isdigit())
    if len(telefono) == 10:
        telefono = "52" + telefono
    elif len(telefono) == 13 and telefono.startswith("521"):
        telefono = "52" + telefono[3:]
    elif not telefono.startswith("52"):
        telefono = "52" + telefono

    # Get folio
    folio = ""
    if pedido_id:
        result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
        pedido = result.scalar_one_or_none()
        if pedido:
            folio = pedido.numero

    headers = {"Authorization": f"Bearer {whapi_token}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Send text message
            texto = f"Hola {nombre}, aqui esta tu comprobante del pedido {folio} 🌸\nGracias por tu preferencia — Floreria Lucy"
            await client.post(
                "https://gate.whapi.cloud/messages/text",
                headers=headers,
                json={"to": telefono, "body": texto},
            )

            # Send ticket image
            if imagen_b64:
                await client.post(
                    "https://gate.whapi.cloud/messages/image",
                    headers=headers,
                    json={"to": telefono, "media": f"data:image/png;base64,{imagen_b64}", "caption": ""},
                )

        return {"ok": True}
    except Exception as e:
        return {"error": f"Error al enviar WhatsApp: {str(e)}"}
