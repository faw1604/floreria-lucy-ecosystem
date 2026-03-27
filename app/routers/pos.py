from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import httpx
import os
from app.database import get_db
from app.models.productos import Producto
from app.models.clientes import Cliente
from app.models.pedidos import Pedido, ItemPedido
from app.models.pagos import MetodoPago
from app.models.funerarias import Funeraria
from app.core.config import TZ
from app.routers.auth import verificar_sesion

router = APIRouter()


async def _generar_folio(db: AsyncSession) -> str:
    año = datetime.now(TZ).strftime("%Y")
    result = await db.execute(select(func.max(Pedido.numero)).where(Pedido.numero.like(f"FL-{año}-%")))
    max_folio = result.scalar()
    if max_folio:
        ultimo_num = int(max_folio.rsplit("-", 1)[1])
    else:
        ultimo_num = 0
    return f"FL-{año}-{str(ultimo_num + 1).zfill(4)}"


@router.get("/productos")
async def pos_productos(
    q: str = "",
    categoria: str = "",
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    query = select(Producto).where(Producto.activo == True, Producto.imagen_url.isnot(None))
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
        codigo_referido=generar_codigo_referido(),
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

    # Tax — IEPS is already included in the price, does NOT add to total
    tipo_impuesto = data.get("tipo_impuesto", "NA")
    impuesto = 0
    if tipo_impuesto == "IVA":
        impuesto = int(subtotal * 0.16)

    # Shipping
    envio = 0
    zona = data.get("zona_envio")
    if tipo == "domicilio" and zona:
        tarifas = {"Morada": 9900, "Azul": 15900, "Verde": 19900}
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

    pedido = Pedido(
        numero=folio,
        customer_id=cliente_id,
        canal="Mostrador",
        estado="Listo" if estado_pedido == "pagado" else "Pendiente pago",
        estado_florista="aprobado" if estado_pedido == "pagado" else "pendiente_pago",
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
        subtotal=subtotal,
        envio=envio,
        total=total,
        tipo_especial="Funeral" if tipo == "funeral" else None,
        ruta=data.get("ruta"),
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

    await db.commit()
    await db.refresh(pedido)

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
        "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None,
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
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    from datetime import date as date_type, time as time_type
    from calendar import monthrange
    ahora = datetime.now(TZ)
    hoy = ahora.date()

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

    # Convert local date boundaries to UTC for DB query (fecha_pedido stored as UTC)
    if skip_date_filter:
        query = select(Pedido).order_by(Pedido.fecha_pedido.desc())
    else:
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
        canal_map = {"POS": "Mostrador", "Claudia": "WhatsApp"}
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
        "pendiente_pago": ["Pendiente pago", "pendiente_pago"],
        "pagado": ["Listo"],
        "listo_taller": ["Listo taller"],
        "en_camino": ["En camino"],
        "entregado": ["Entregado"],
        "cancelado": ["Cancelado"],
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
        data["fecha_pedido"] = p.fecha_pedido.strftime("%Y-%m-%d %H:%M") if p.fecha_pedido else None
        if p.estado in ("Pendiente pago", "pendiente_pago"):
            pendientes.append(data)
        else:
            finalizados.append(data)
            total_vendido += p.total or 0
            for metodo in (p.forma_pago or "").split(", "):
                metodo = metodo.strip()
                if metodo:
                    desglose_pago[metodo] = desglose_pago.get(metodo, 0) + (p.total or 0)

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


@router.patch("/pedido/{pedido_id}/finalizar")
async def pos_finalizar_pedido(
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
    pagos = data.get("pagos", [])
    suma_pagos = sum(p["monto"] for p in pagos)
    if suma_pagos < (pedido.total or 0):
        raise HTTPException(status_code=400, detail=f"Falta asignar ${((pedido.total or 0) - suma_pagos) / 100:.0f}")

    pedido.estado = "Listo"
    pedido.estado_florista = "aprobado"
    pedido.pago_confirmado = True
    pedido.forma_pago = ", ".join(p.get("nombre", "") for p in pagos if p.get("nombre"))
    await db.commit()
    return {"ok": True, "folio": pedido.numero, "estado": pedido.estado}


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
    impuesto = int(subtotal * 0.16) if tipo_impuesto == "IVA" else 0
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
        tarifas = {"Morada": 9900, "Azul": 15900, "Verde": 19900}
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

    # Update pedido fields
    pedido.estado = "Listo" if estado_pedido == "pagado" else "Pendiente pago"
    pedido.estado_florista = "aprobado" if estado_pedido == "pagado" else "pendiente_pago"
    pedido.pago_confirmado = estado_pedido == "pagado"
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

    estados_venta = ["Listo", "Listo taller", "En camino", "Entregado"]

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
    if not telefono.startswith("52"):
        telefono = "52" + telefono
    mensaje = data.get("mensaje", "")
    if not mensaje.strip():
        return {"error": "Mensaje vacio"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                "https://gate.whapi.cloud/messages/text",
                headers={"Authorization": f"Bearer {whapi_token}", "Content-Type": "application/json"},
                json={"to": telefono, "body": mensaje},
            )
        return {"ok": True}
    except Exception as e:
        return {"error": f"Error al enviar: {str(e)}"}


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

    # Format phone: digits only, prepend 52 if needed
    telefono = "".join(c for c in telefono if c.isdigit())
    if not telefono.startswith("52"):
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
