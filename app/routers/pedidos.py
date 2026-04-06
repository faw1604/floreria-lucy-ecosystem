from fastapi import APIRouter, Depends, HTTPException, Cookie, Header, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import os, logging
import cloudinary
import cloudinary.uploader
from app.database import get_db
from app.models.pedidos import Pedido, ItemPedido
from app.models.clientes import Cliente
from app.models.productos import Producto
from app.models.configuracion import ConfiguracionNegocio
from app.core.config import TZ
from app.core.estados import EstadoPedido as EP
from app.routers.auth import verificar_sesion

logger = logging.getLogger("floreria")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "ddku2wmpk"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "543563876228939"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
)

router = APIRouter()


async def _serializar_pedido_con_items(p, db):
    """Serializa un pedido incluyendo sus items con info de producto."""
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
    return {
        "id": p.id, "numero": p.numero, "estado": p.estado, "canal": p.canal,
        "total": p.total, "horario_entrega": p.horario_entrega, "hora_exacta": p.hora_exacta,
        "receptor_nombre": p.receptor_nombre, "receptor_telefono": p.receptor_telefono,
        "direccion_entrega": p.direccion_entrega, "dedicatoria": p.dedicatoria,
        "notas_internas": p.notas_internas, "requiere_humano": p.requiere_humano,
        "tipo_especial": p.tipo_especial, "pago_confirmado": p.pago_confirmado,
        "zona_entrega": p.zona_entrega, "forma_pago": p.forma_pago,
        "estado_florista": p.estado_florista, "nota_florista": p.nota_florista,
        "requiere_factura": p.requiere_factura,
        "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None,
        "items": items,
    }


async def generar_numero_pedido(db: AsyncSession) -> str:
    from app.core.utils import generar_folio
    return await generar_folio(db)

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
    return [await _serializar_pedido_con_items(p, db) for p in pedidos]

@router.get("/manana")
async def pedidos_de_manana(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    manana = datetime.now(TZ).date() + timedelta(days=1)
    result = await db.execute(
        select(Pedido)
        .where(Pedido.fecha_entrega == manana)
        .order_by(Pedido.horario_entrega)
    )
    pedidos = result.scalars().all()
    return [await _serializar_pedido_con_items(p, db) for p in pedidos]

@router.get("/agendados")
async def pedidos_agendados(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    pasado_manana = datetime.now(TZ).date() + timedelta(days=2)
    result = await db.execute(
        select(Pedido)
        .where(Pedido.fecha_entrega >= pasado_manana)
        .order_by(Pedido.fecha_entrega, Pedido.horario_entrega)
    )
    pedidos = result.scalars().all()
    return [{"id": p.id, "numero": p.numero, "estado": p.estado, "canal": p.canal, "total": p.total, "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None, "horario_entrega": p.horario_entrega, "receptor_nombre": p.receptor_nombre, "tipo_especial": p.tipo_especial, "pago_confirmado": p.pago_confirmado, "zona_entrega": p.zona_entrega} for p in pedidos]

@router.get("/realizados")
async def pedidos_realizados(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(Pedido)
        .where(Pedido.estado == "Listo")
        .order_by(Pedido.fecha_entrega.desc())
    )
    pedidos = result.scalars().all()
    return [{"id": p.id, "numero": p.numero, "estado": p.estado, "canal": p.canal, "total": p.total, "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None, "horario_entrega": p.horario_entrega, "hora_exacta": p.hora_exacta, "receptor_nombre": p.receptor_nombre, "receptor_telefono": p.receptor_telefono, "direccion_entrega": p.direccion_entrega, "dedicatoria": p.dedicatoria, "notas_internas": p.notas_internas, "tipo_especial": p.tipo_especial, "pago_confirmado": p.pago_confirmado, "zona_entrega": p.zona_entrega, "forma_pago": p.forma_pago} for p in pedidos]

@router.get("/desde-claudia/test")
async def claudia_test():
    return {"ok": True, "api": "floreria-lucy-ecosystem"}




@router.get("/estado-cliente/{telefono}")
async def estado_pedido_cliente(
    telefono: str,
    x_claudia_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Claudia consulta el pedido más reciente de un cliente por teléfono."""
    expected_key = os.getenv("CLAUDIA_API_KEY", "")
    if not expected_key or x_claudia_key != expected_key:
        raise HTTPException(status_code=401, detail="API key inválida")

    # Buscar cliente por teléfono (probar con y sin prefijo 521)
    cliente = None
    for tel in [telefono, telefono.lstrip("521"), telefono.lstrip("52")]:
        result = await db.execute(select(Cliente).where(Cliente.telefono == tel))
        cliente = result.scalar_one_or_none()
        if cliente:
            break

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Pedido más reciente
    from app.core.estados import EP
    result = await db.execute(
        select(Pedido)
        .where(Pedido.customer_id == cliente.id)
        .order_by(Pedido.id.desc())
        .limit(1)
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Sin pedidos")

    return {
        "id": pedido.id,
        "folio": pedido.numero,
        "estado": pedido.estado,
        "estado_florista": pedido.estado_florista,
        "fecha_entrega": str(pedido.fecha_entrega) if pedido.fecha_entrega else None,
        "total": pedido.total,
        "pago_confirmado": pedido.pago_confirmado,
    }

@router.post("/desde-claudia")
async def crear_pedido_desde_claudia(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_claudia_key: str | None = Header(default=None),
):
    # Verificar API key
    expected_key = os.getenv("CLAUDIA_API_KEY", "")
    if not expected_key or x_claudia_key != expected_key:
        raise HTTPException(status_code=401, detail="API key inválida")

    data = await request.json()

    # 1. Buscar o crear cliente
    telefono_raw = data.get("telefono_cliente", "")
    digitos = "".join(c for c in telefono_raw if c.isdigit())
    if len(digitos) > 10 and digitos.startswith("52"):
        digitos = digitos[2:]

    cliente = None
    if digitos:
        result = await db.execute(select(Cliente).where(Cliente.telefono == digitos))
        cliente = result.scalar_one_or_none()

    if not cliente:
        cliente = Cliente(
            nombre=data.get("nombre_cliente", "Cliente WhatsApp"),
            telefono=digitos or f"sin-{datetime.now(TZ).strftime('%Y%m%d%H%M%S')}",
            fuente="WhatsApp",
        )
        db.add(cliente)
        await db.flush()

    # 2. Buscar o crear producto
    producto = None
    codigo = data.get("producto_codigo")
    nombre_prod = data.get("producto_nombre", "")
    if codigo:
        result = await db.execute(select(Producto).where(Producto.codigo == codigo))
        producto = result.scalar_one_or_none()
    if not producto and nombre_prod:
        result = await db.execute(select(Producto).where(Producto.nombre == nombre_prod))
        producto = result.scalar_one_or_none()
    if not producto:
        producto = Producto(
            codigo=codigo,
            nombre=nombre_prod or "Producto WhatsApp",
            categoria="WhatsApp",
            precio=data.get("precio_producto", 0),
            costo=0,
            activo=True,
            disponible_hoy=True,
        )
        db.add(producto)
        await db.flush()

    # 3. Calcular totales
    modalidad = data.get("modalidad", "domicilio")
    precio_producto = data.get("precio_producto", producto.precio)
    if modalidad == "recoger":
        costo_envio = 0
        zona = None
        direccion = data.get("direccion_entrega")
    else:
        costo_envio = data.get("costo_envio", 0)
        zona = data.get("zona_entrega")
        direccion = data.get("direccion_entrega")

    total = precio_producto + costo_envio

    # 4. Crear pedido
    numero = await generar_numero_pedido(db)
    pedido = Pedido(
        numero=numero,
        customer_id=cliente.id,
        canal=data.get("canal", "WhatsApp"),
        estado=EP.ESPERANDO_VALIDACION,
        fecha_entrega=data.get("fecha_entrega"),
        horario_entrega=data.get("horario_entrega"),
        zona_entrega=zona,
        direccion_entrega=direccion,
        receptor_nombre=data.get("receptor_nombre"),
        receptor_telefono=data.get("receptor_telefono"),
        dedicatoria=data.get("dedicatoria"),
        notas_internas=data.get("notas_internas"),
        forma_pago=data.get("forma_pago"),
        pago_confirmado=False,
        subtotal=precio_producto,
        envio=costo_envio,
        total=total,
        requiere_humano=data.get("requiere_humano", False),
        tipo_especial=data.get("tipo_especial"),
    )
    db.add(pedido)

    # 5. Crear item del pedido
    await db.flush()
    item = ItemPedido(
        pedido_id=pedido.id,
        producto_id=producto.id,
        cantidad=1,
        precio_unitario=precio_producto,
    )
    db.add(item)

    await db.commit()
    await db.refresh(pedido)

    return {
        "ok": True,
        "numero_pedido": pedido.numero,
        "id_pedido": pedido.id,
        "cliente_id": cliente.id,
        "mensaje": f"Pedido {pedido.numero} registrado correctamente",
    }

@router.get("/{pedido_id}/items")
async def obtener_items_pedido(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(ItemPedido).where(ItemPedido.pedido_id == pedido_id)
    )
    items = result.scalars().all()
    productos = []
    for item in items:
        prod = None
        if item.producto_id:
            prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
            prod = prod_result.scalar_one_or_none()
        if prod:
            productos.append({
                "id": prod.id,
                "codigo": prod.codigo,
                "nombre": prod.nombre,
                "imagen_url": prod.imagen_url,
                "cantidad": item.cantidad,
                "precio_unitario": item.precio_unitario,
                "es_personalizado": item.es_personalizado,
                "nombre_personalizado": item.nombre_personalizado,
                "observaciones": item.observaciones,
            })
        elif item.es_personalizado or item.nombre_personalizado:
            # Item personalizado (sin producto_id o producto eliminado)
            productos.append({
                "id": None,
                "codigo": None,
                "nombre": item.nombre_personalizado or "Producto personalizado",
                "imagen_url": None,
                "cantidad": item.cantidad,
                "precio_unitario": item.precio_unitario,
                "es_personalizado": True,
                "nombre_personalizado": item.nombre_personalizado,
                "observaciones": item.observaciones,
            })
    return productos

@router.get("/{pedido_id}/ticket-digital")
async def ticket_digital(
    pedido_id: int,
    db: AsyncSession = Depends(get_db)
):
    from fastapi.responses import HTMLResponse
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Get items
    items_result = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == pedido_id))
    items_db = items_result.scalars().all()
    items_html = ""
    for item in items_db:
        prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
        prod = prod_result.scalar_one_or_none()
        nombre = item.nombre_personalizado if item.es_personalizado and item.nombre_personalizado else (prod.nombre if prod else "Producto")
        precio = f"${item.precio_unitario * item.cantidad // 100:,}"
        items_html += f'<tr><td style="padding:6px 0;border-bottom:1px solid #eee">{item.cantidad}x {nombre}</td><td style="padding:6px 0;border-bottom:1px solid #eee;text-align:right">{precio}</td></tr>'

    if not items_html:
        items_html = '<tr><td style="padding:6px 0" colspan="2">Sin detalle de productos</td></tr>'

    fecha_pedido = pedido.fecha_pedido.strftime("%d/%m/%Y") if pedido.fecha_pedido else ""
    fecha_entrega = ""
    if pedido.fecha_entrega:
        from datetime import datetime as dt
        fecha_entrega = dt.combine(pedido.fecha_entrega, dt.min.time()).strftime("%d/%m/%Y")

    recoger = not pedido.direccion_entrega and not pedido.zona_entrega
    horario_map = {"manana": "Mañana 9-2pm", "mañana": "Mañana 9-2pm", "tarde": "Tarde 2-6pm", "noche": "Noche 6-9pm"}
    horario = horario_map.get((pedido.horario_entrega or "").lower(), pedido.horario_entrega or "")

    if recoger:
        entrega_html = f"""
        <p style="margin:4px 0"><strong>Modalidad:</strong> Recoger en tienda</p>
        <p style="margin:4px 0"><strong>Cliente:</strong> {pedido.receptor_nombre or ''}</p>
        {"<p style='margin:4px 0'><strong>Hora aprox:</strong> " + pedido.hora_exacta + "</p>" if pedido.hora_exacta else ""}
        """
    else:
        entrega_html = f"""
        <p style="margin:4px 0"><strong>Horario:</strong> {horario}</p>
        {"<p style='margin:4px 0'><strong>Zona:</strong> " + pedido.zona_entrega + "</p>" if pedido.zona_entrega else ""}
        <p style="margin:4px 0"><strong>Recibe:</strong> {pedido.receptor_nombre or ''}</p>
        {"<p style='margin:4px 0'><strong>Tel:</strong> " + pedido.receptor_telefono + "</p>" if pedido.receptor_telefono else ""}
        {"<p style='margin:4px 0'><strong>Direccion:</strong> " + pedido.direccion_entrega + "</p>" if pedido.direccion_entrega else ""}
        """

    total_display = f"${pedido.total // 100:,}" if pedido.total else "$0"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f5f5">
<div style="max-width:400px;margin:20px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1)">
  <div style="background:#193a2c;color:#fff;padding:24px;text-align:center">
    <div style="font-size:22px;font-weight:700;letter-spacing:1px">Floreria Lucy</div>
    <div style="font-size:13px;opacity:.8;font-style:italic;margin-top:4px">La expresion del amor</div>
  </div>
  <div style="padding:20px">
    <div style="text-align:center;margin-bottom:16px">
      <div style="font-size:18px;font-weight:700;color:#193a2c">Pedido {pedido.numero}</div>
      <div style="font-size:12px;color:#888;margin-top:4px">Fecha del pedido: {fecha_pedido}</div>
    </div>
    <div style="background:#f9f7f4;border-radius:8px;padding:12px;margin-bottom:16px">
      <div style="font-size:13px;font-weight:600;color:#193a2c;margin-bottom:8px">Datos de entrega</div>
      <div style="font-size:13px;color:#333">
        {"<p style='margin:4px 0'><strong>Fecha entrega:</strong> " + fecha_entrega + "</p>" if fecha_entrega else ""}
        {entrega_html}
      </div>
    </div>
    <table style="width:100%;font-size:13px;border-collapse:collapse;margin-bottom:16px">
      <thead><tr><td style="padding:6px 0;font-weight:600;border-bottom:2px solid #193a2c">Producto</td><td style="padding:6px 0;font-weight:600;border-bottom:2px solid #193a2c;text-align:right">Precio</td></tr></thead>
      <tbody>{items_html}</tbody>
    </table>
    <div style="text-align:right;font-size:18px;font-weight:700;color:#193a2c;padding:8px 0;border-top:2px solid #193a2c">
      Total: {total_display}
    </div>
  </div>
  <div style="background:#f9f7f4;padding:16px;text-align:center;font-size:12px;color:#888">
    <div style="margin-bottom:4px">Gracias por tu compra 🌸</div>
    <div>Tel: 614 334 9392 | C. Sabino 610, Las Granjas, Chihuahua</div>
  </div>
</div>
</body></html>"""
    return HTMLResponse(html)

@router.get("/{pedido_id}/ruta")
async def obtener_ruta_pedido(
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
    if not pedido.direccion_entrega:
        return {"ruta": None, "error": "El pedido no tiene dirección de entrega"}

    import httpx
    import logging
    from app.services.rutas import obtener_ruta

    logger = logging.getLogger("floreria")
    ua = "FloreriaLucy/1.0 florerialucychihuahua@gmail.com"
    direccion = pedido.direccion_entrega
    logger.info(f"[RUTA] Direccion original: '{direccion}'")

    # Extraer calle (antes de la primera coma = sin colonia)
    calle = direccion.split(",")[0].strip()
    logger.info(f"[RUTA] Street extraida: '{calle}'")

    async def geocode(street: str) -> list:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "street": street,
            "city": "Chihuahua",
            "state": "Chihuahua",
            "country": "Mexico",
            "countrycodes": "mx",
            "bounded": "1",
            "viewbox": "-106.25,28.83,-105.92,28.55",
            "format": "json",
            "limit": "1",
        }
        logger.info(f"[RUTA] GET {url} street='{street}' city=Chihuahua")
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=params, headers={"User-Agent": ua}, timeout=10)
            data = r.json()
            logger.info(f"[RUTA] Nominatim response ({r.status_code}): {data}")
            return data

    try:
        data = await geocode(calle)

        # Retry with full address as free-form if structured fails
        if not data:
            logger.info(f"[RUTA] Reintentando con direccion completa como q=")
            url = "https://nominatim.openstreetmap.org/search"
            async with httpx.AsyncClient() as client:
                r = await client.get(url, params={
                    "q": f"{direccion}, Chihuahua, Mexico",
                    "countrycodes": "mx",
                    "bounded": "1",
                    "viewbox": "-106.25,28.83,-105.92,28.55",
                    "format": "json",
                    "limit": "1",
                }, headers={"User-Agent": ua}, timeout=10)
                data = r.json()
                logger.info(f"[RUTA] Nominatim fallback response ({r.status_code}): {data}")
    except Exception as e:
        logger.error(f"[RUTA] Error geocoding: {e}")
        return {"ruta": None, "error": f"Error al conectar con el geocodificador: {str(e)}"}

    if not data:
        return {"ruta": None, "error": "No se pudo geocodificar la dirección", "street": calle}

    lat = float(data[0]["lat"])
    lng = float(data[0]["lon"])
    display = data[0].get("display_name", "")
    ruta = obtener_ruta(lat, lng)

    if ruta and pedido.ruta != ruta:
        pedido.ruta = ruta
        await db.commit()

    return {"ruta": ruta, "lat": lat, "lng": lng, "display_name": display}

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
    estado_anterior = pedido.estado
    pedido.estado = request.get("estado", pedido.estado)
    pedido.pago_confirmado = request.get("pago_confirmado", pedido.pago_confirmado)
    if "estado_florista" in request:
        pedido.estado_florista = request["estado_florista"]
    if "nota_florista" in request:
        pedido.nota_florista = request["nota_florista"]
    if "requiere_humano" in request:
        pedido.requiere_humano = request["requiere_humano"]
    if "nota_validacion" in request:
        pedido.nota_validacion = request["nota_validacion"]
    await db.commit()
    # Fire webhook si cambió el estado
    if pedido.webhook_url and pedido.estado != estado_anterior:
        _disparar_webhook(pedido.webhook_url, pedido.numero, estado_anterior, pedido.estado)
    return {"id": pedido.id, "numero": pedido.numero, "estado": pedido.estado, "estado_florista": pedido.estado_florista}


def _disparar_webhook(url: str, folio: str, estado_anterior: str, estado_nuevo: str, extra: dict | None = None):
    """Fire-and-forget webhook notification."""
    import asyncio
    import httpx

    async def _send():
        try:
            payload = {
                "folio": folio,
                "estado_anterior": estado_anterior,
                "estado_nuevo": estado_nuevo,
            }
            if extra:
                payload.update(extra)
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.warning(f"Webhook falló para {folio}: {e}")

    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_send())
    except RuntimeError:
        pass


# --- Endpoints flujo WhatsApp ---

@router.post("/{pedido_id}/confirmar-pago")
async def confirmar_pago(
    pedido_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Admin confirma el pago de un pedido con comprobante recibido."""
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if pedido.estado not in (EP.COMPROBANTE_RECIBIDO, EP.PENDIENTE_PAGO, "pendiente_pago"):
        raise HTTPException(status_code=400, detail=f"Estado actual '{pedido.estado}' no permite confirmar pago")

    estado_anterior = pedido.estado
    pedido.estado = "pagado"
    pedido.pago_confirmado = True
    pedido.pago_confirmado_at = datetime.now(TZ)
    pedido.pago_confirmado_por = "admin"
    await db.commit()

    if pedido.webhook_url:
        # Obtener teléfono cliente
        tel_cliente = None
        if pedido.customer_id:
            cli_r = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cli = cli_r.scalar_one_or_none()
            tel_cliente = cli.telefono if cli else None
        _disparar_webhook(pedido.webhook_url, pedido.numero, estado_anterior, "pagado", extra={
            "accion": "pago_confirmado",
            "telefono_cliente": tel_cliente,
            "fecha_entrega": str(pedido.fecha_entrega) if pedido.fecha_entrega else None,
        })
    elif pedido.canal == "Web" and pedido.tracking_token and pedido.customer_id:
        try:
            cli_r = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cli = cli_r.scalar_one_or_none()
            if cli and cli.telefono:
                tracking_url = f"https://www.florerialucy.com/catalogo/seguimiento.html?token={pedido.tracking_token}"
                from app.routers.catalogo import _enviar_whatsapp
                await _enviar_whatsapp(cli.telefono,
                    f"Hola {cli.nombre.split()[0]} 🌸\n\n"
                    f"Tu pago para el pedido {pedido.numero} fue confirmado! Tu arreglo sera elaborado pronto.\n\n"
                    f"Sigue el estatus aqui:\n{tracking_url}"
                )
        except Exception:
            pass

    return {"ok": True, "folio": pedido.numero}


@router.post("/{pedido_id}/subir-comprobante")
async def subir_comprobante(
    pedido_id: int,
    comprobante: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    x_api_key: str | None = Header(default=None),
):
    """Claudia sube comprobante de pago del cliente."""
    expected_key = os.getenv("CLAUDIA_API_KEY", "")
    if not expected_key or x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="API key inválida")

    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Subir a Cloudinary
    contents = await comprobante.read()
    upload_result = cloudinary.uploader.upload(
        contents,
        folder="comprobantes",
        public_id=f"comp_{pedido.numero}_{datetime.now(TZ).strftime('%Y%m%d%H%M%S')}",
    )
    url = upload_result["secure_url"]

    estado_anterior = pedido.estado
    pedido.comprobante_pago_url = url
    pedido.comprobante_pago_at = datetime.now(TZ)
    pedido.estado = "comprobante_recibido"
    await db.commit()

    if pedido.webhook_url:
        _disparar_webhook(pedido.webhook_url, pedido.numero, estado_anterior, "comprobante_recibido")

    return {"ok": True, "url": url}


@router.post("/{pedido_id}/marcar-comprobante-recibido")
async def marcar_comprobante_recibido(
    pedido_id: int,
    db: AsyncSession = Depends(get_db),
    x_claudia_key: str | None = Header(default=None),
):
    """Claudia marca que el cliente mandó comprobante (sin subir imagen).
    Notifica a Fer por WhatsApp para que revise y confirme el pago."""
    from app.core.utils import ahora
    from app.core.estados import EstadoPedido as EP

    expected_key = os.getenv("CLAUDIA_API_KEY", "")
    if not expected_key or x_claudia_key != expected_key:
        raise HTTPException(status_code=401, detail="API key inválida")

    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Permitir desde pendiente_pago o comprobante_recibido (idempotente)
    if pedido.estado not in (EP.PENDIENTE_PAGO, "pendiente_pago", EP.COMPROBANTE_RECIBIDO):
        raise HTTPException(
            status_code=400,
            detail=f"El pedido no está en estado pendiente_pago (actual: {pedido.estado})"
        )

    # Cambiar estado
    pedido.estado = EP.COMPROBANTE_RECIBIDO
    pedido.comprobante_pago_at = ahora()

    # Obtener nombre del cliente
    cli_nombre = "Cliente"
    if pedido.customer_id:
        cli_r = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
        cli = cli_r.scalar_one_or_none()
        if cli and cli.nombre:
            cli_nombre = cli.nombre

    await db.commit()

    # Notificar a Fer en background
    import asyncio
    telefono_negocio = os.getenv("WHATSAPP_NEGOCIO", "5216143349392")
    total_fmt = f"${(pedido.total or 0)/100:,.0f}"
    msg = (
        f"💳 Comprobante recibido — {pedido.numero} | "
        f"{cli_nombre} | {total_fmt} | {pedido.forma_pago or 'Sin método'} "
        f"— Revisa en POS → Pendientes."
    )

    async def _notify():
        try:
            from app.routers.catalogo import _enviar_whatsapp
            await _enviar_whatsapp(telefono_negocio, msg)
        except Exception:
            pass
    asyncio.create_task(_notify())

    return {"ok": True, "folio": pedido.numero}


ESTADO_LABELS = {
    EP.ESPERANDO_VALIDACION: "Esperando validación del florista",
    "pendiente_pago": "Validado por el florista",
    EP.PENDIENTE_PAGO: "Validado por el florista",
    EP.COMPROBANTE_RECIBIDO: "Comprobante de pago recibido",
    EP.PAGADO: "Pago confirmado",
    EP.EN_PRODUCCION: "En producción",
    EP.LISTO: "Listo para entrega",
    EP.LISTO_TALLER: "Listo en taller",
    EP.EN_CAMINO: "En camino",
    EP.ENTREGADO: "Entregado",
    "rechazado": "Rechazado por el florista",
    EP.CANCELADO: "Cancelado",
}


@router.get("/{pedido_id}/estado-para-claudia")
async def estado_para_claudia(
    pedido_id: int,
    db: AsyncSession = Depends(get_db),
    x_api_key: str | None = Header(default=None),
):
    """Claudia consulta estado del pedido para notificar al cliente."""
    expected_key = os.getenv("CLAUDIA_API_KEY", "")
    if not expected_key or x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="API key inválida")

    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Obtener teléfono del cliente
    telefono = None
    if pedido.customer_id:
        cli_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
        cliente = cli_result.scalar_one_or_none()
        if cliente:
            telefono = cliente.telefono

    # Datos de pago solo cuando estado = pendiente_pago
    datos_pago = None
    if pedido.estado in ("pendiente_pago", EP.PENDIENTE_PAGO):
        from app.routers.configuracion import obtener_config_dict
        config = await obtener_config_dict(db)
        datos_pago = {
            "banco": config.get("banco_nombre", ""),
            "cuenta": config.get("banco_cuenta", ""),
            "clabe": config.get("banco_clabe", ""),
            "titular": config.get("banco_titular", ""),
            "concepto": config.get("banco_concepto", ""),
        }

    return {
        "folio": pedido.numero,
        "estado": pedido.estado,
        "estado_label": ESTADO_LABELS.get(pedido.estado, pedido.estado),
        "cliente_telefono": telefono,
        "total": pedido.total,
        "nota_validacion": pedido.nota_validacion,
        "datos_pago": datos_pago,
    }


@router.post("/{pedido_id}/webhook-estado")
async def registrar_webhook(
    pedido_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_api_key: str | None = Header(default=None),
):
    """Claudia registra URL de webhook para recibir cambios de estado."""
    expected_key = os.getenv("CLAUDIA_API_KEY", "")
    if not expected_key or x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="API key inválida")

    data = await request.json()
    webhook_url = data.get("webhook_url")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url requerido")

    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    pedido.webhook_url = webhook_url
    await db.commit()
    return {"ok": True, "folio": pedido.numero}
