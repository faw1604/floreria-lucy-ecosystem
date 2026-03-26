from fastapi import APIRouter, Depends, HTTPException, Cookie, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import os
from app.database import get_db
from app.models.pedidos import Pedido, ItemPedido
from app.models.clientes import Cliente
from app.models.productos import Producto
from app.core.config import TZ
from app.routers.auth import verificar_sesion

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
        "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None,
        "items": items,
    }


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
        estado="Pendiente pago",
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
    return productos

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
    if "estado_florista" in request:
        pedido.estado_florista = request["estado_florista"]
    if "nota_florista" in request:
        pedido.nota_florista = request["nota_florista"]
    if "requiere_humano" in request:
        pedido.requiere_humano = request["requiere_humano"]
    await db.commit()
    return {"id": pedido.id, "numero": pedido.numero, "estado": pedido.estado, "estado_florista": pedido.estado_florista}
