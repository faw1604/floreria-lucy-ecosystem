from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import httpx
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
    result = await db.execute(select(Pedido).where(Pedido.numero.like(f"FL-{año}-%")))
    count = len(result.scalars().all())
    return f"FL-{año}-{str(count + 1).zfill(4)}"


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
    return {"lat": lat, "lng": lng, "ruta": ruta, "display_name": data[0].get("display_name", "")}


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

    # Validate funeral products
    if tipo == "funeral":
        for item in items:
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
        mp = (await db.execute(select(MetodoPago).where(MetodoPago.id == pago["metodo_pago_id"]))).scalar_one_or_none()
        if mp and "link" in (mp.tipo or "").lower():
            comision = int(pago["monto"] * 0.04)

    total = subtotal + impuesto + envio - descuento + comision

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
        total = subtotal + impuesto + envio - descuento + comision

    folio = await _generar_folio(db)
    horario = data.get("horario_entrega")
    if horario == "hora_especifica":
        horario = None

    pedido = Pedido(
        numero=folio,
        customer_id=cliente_id,
        canal="Mostrador",
        estado="Listo" if estado_pedido == "pagado" else "Pendiente pago",
        estado_florista="aprobado" if estado_pedido == "pagado" else None,
        fecha_entrega=datetime.now(TZ).date(),
        horario_entrega=horario,
        hora_exacta=data.get("hora_especifica"),
        zona_entrega=zona,
        direccion_entrega=data.get("direccion_entrega"),
        receptor_nombre=data.get("nombre_destinatario"),
        receptor_telefono=data.get("telefono_destinatario"),
        dedicatoria=data.get("dedicatoria"),
        notas_internas=notas or None,
        forma_pago=", ".join([str(p.get("metodo_pago_id", "")) for p in pagos]) if pagos else "Efectivo",
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
            producto_id=it["producto_id"],
            cantidad=it["cantidad"],
            precio_unitario=it["precio_unitario"],
        ))

    await db.commit()
    await db.refresh(pedido)

    return {
        "ok": True, "folio": pedido.numero, "id": pedido.id,
        "total": total, "subtotal": subtotal, "impuesto": impuesto,
        "envio": envio, "descuento": descuento, "comision": comision,
        "estado": pedido.estado,
    }
