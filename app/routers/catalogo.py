from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import os, logging, httpx
from app.database import get_db
from app.models.productos import Producto
from app.models.pedidos import Pedido, ItemPedido
from app.models.clientes import Cliente
from app.models.configuracion import HorarioEspecifico, CodigoDescuento
from app.core.config import TZ
from datetime import date as date_type

logger = logging.getLogger("floreria")

FUNERAL_CATS = ['funeral', 'conjuntos funebres', 'conjuntos fúnebres']

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def catalogo_html():
    try:
        with open("app/catalogo.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="catalogo.html no encontrado")

@router.get("/historia", response_class=HTMLResponse)
async def historia_html():
    try:
        with open("app/pages/historia.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

@router.get("/contacto", response_class=HTMLResponse)
async def contacto_html():
    try:
        with open("app/pages/contacto.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

@router.get("/facturacion", response_class=HTMLResponse)
async def facturacion_html():
    try:
        with open("app/pages/facturacion.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

@router.get("/legal", response_class=HTMLResponse)
async def legal_html():
    try:
        with open("app/pages/legal.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")

@router.get("/productos")
async def catalogo_productos(
    categoria: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Producto)
        .where(
            Producto.activo == True,
            Producto.disponible_hoy == True,
            Producto.imagen_url.isnot(None),
        )
        .order_by(Producto.categoria, Producto.nombre)
    )
    if categoria:
        query = query.where(Producto.categoria == categoria)
    result = await db.execute(query)
    productos = result.scalars().all()
    return [
        {
            "id": p.id,
            "codigo": p.codigo,
            "nombre": p.nombre,
            "categoria": p.categoria,
            "precio": p.precio,
            "precio_descuento": p.precio_descuento,
            "precio_display": f"${p.precio // 100:,}",
            "precio_descuento_display": f"${p.precio_descuento // 100:,}" if p.precio_descuento else None,
            "descripcion": p.descripcion,
            "imagen_url": p.imagen_url,
            "disponible_hoy": p.disponible_hoy,
            "etiquetas": p.etiquetas,
            "dimensiones": p.dimensiones,
            "medida_alto": float(p.medida_alto) if p.medida_alto else None,
            "medida_ancho": float(p.medida_ancho) if p.medida_ancho else None,
        }
        for p in productos
    ]


@router.get("/horarios-disponibles")
async def horarios_disponibles(
    fecha: str,
    db: AsyncSession = Depends(get_db),
):
    """Retorna horas específicas disponibles para una fecha dada."""
    try:
        fecha_dt = date_type.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido (YYYY-MM-DD)")

    hoy = datetime.now(TZ).date()
    if fecha_dt <= hoy:
        return []  # Solo mañana o después

    # Python weekday: 0=Monday..6=Sunday — coincide con nuestro esquema
    dia_semana = fecha_dt.weekday()

    result = await db.execute(
        select(HorarioEspecifico)
        .where(HorarioEspecifico.dia_semana == dia_semana, HorarioEspecifico.activo == True)
        .order_by(HorarioEspecifico.hora)
    )
    horarios = result.scalars().all()
    return [{"hora": h.hora, "disponible": True} for h in horarios]


@router.get("/validar-descuento")
async def validar_descuento(
    codigo: str,
    db: AsyncSession = Depends(get_db),
):
    """Valida un código de descuento."""
    codigo_upper = codigo.strip().upper()
    result = await db.execute(
        select(CodigoDescuento).where(CodigoDescuento.codigo == codigo_upper)
    )
    desc = result.scalar_one_or_none()
    if not desc or not desc.activo:
        return {"valido": False}
    # Verificar expiración
    if desc.fecha_expiracion:
        hoy = datetime.now(TZ).date()
        if hoy > desc.fecha_expiracion:
            return {"valido": False}
    # Verificar usos
    if desc.usos_maximos is not None and desc.usos_actuales >= desc.usos_maximos:
        return {"valido": False}
    return {
        "valido": True,
        "tipo": desc.tipo,
        "valor": desc.valor,
        "descripcion": desc.descripcion or f"{desc.valor}{'%' if desc.tipo == 'porcentaje' else ' pesos'} de descuento",
    }


async def _generar_numero_pedido(db: AsyncSession) -> str:
    ahora = datetime.now(TZ)
    año = ahora.strftime("%Y")
    result = await db.execute(select(Pedido).where(Pedido.numero.like(f"FL-{año}-%")))
    count = len(result.scalars().all())
    return f"FL-{año}-{str(count + 1).zfill(4)}"


def _formatear_telefono(tel: str) -> str:
    """Normaliza teléfono a 10 dígitos (sin prefijo 52)."""
    digitos = "".join(c for c in tel if c.isdigit())
    if len(digitos) > 10 and digitos.startswith("52"):
        digitos = digitos[2:]
    return digitos


async def _enviar_whatsapp(telefono: str, mensaje: str):
    """Envía mensaje WhatsApp vía Whapi. Fire-and-forget."""
    token = os.getenv("WHAPI_TOKEN", "")
    if not token:
        logger.warning("[WHAPI] No hay WHAPI_TOKEN configurado")
        return
    chat_id = f"52{telefono}@s.whatsapp.net"
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://gate.whapi.cloud/messages/text",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"to": chat_id, "body": mensaje},
                timeout=15,
            )
        logger.info(f"[WHAPI] WhatsApp enviado a {telefono}")
    except Exception as e:
        logger.error(f"[WHAPI] Error enviando WhatsApp: {e}")


@router.post("/pedido")
async def crear_pedido_web(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Endpoint público para crear pedido desde el catálogo web."""
    data = await request.json()

    tipo = data.get("tipo", "domicilio")
    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Debes agregar al menos un producto")

    # Validar campos obligatorios
    nombre_cliente = (data.get("cliente_nombre") or "").strip()
    telefono_raw = (data.get("cliente_telefono") or "").strip()
    if not nombre_cliente or len(nombre_cliente) < 3:
        raise HTTPException(status_code=400, detail="Nombre del cliente es obligatorio (mínimo 3 caracteres)")
    if not telefono_raw:
        raise HTTPException(status_code=400, detail="Teléfono del cliente es obligatorio")

    telefono = _formatear_telefono(telefono_raw)
    if len(telefono) < 10:
        raise HTTPException(status_code=400, detail="Teléfono inválido")

    fecha_entrega = data.get("fecha_entrega")
    if not fecha_entrega:
        raise HTTPException(status_code=400, detail="Fecha de entrega es obligatoria")

    # Validar tipo domicilio
    if tipo == "domicilio":
        if not data.get("nombre_destinatario"):
            raise HTTPException(status_code=400, detail="Nombre de quien recibe es obligatorio")
        if not data.get("telefono_destinatario"):
            raise HTTPException(status_code=400, detail="Teléfono de quien recibe es obligatorio")
        if not data.get("direccion_entrega"):
            raise HTTPException(status_code=400, detail="Dirección de entrega es obligatoria")

    # Validar tipo funeral
    if tipo == "funeral":
        if not data.get("nombre_fallecido"):
            raise HTTPException(status_code=400, detail="Nombre del fallecido es obligatorio")

    # Verificar productos existen y calcular subtotal
    subtotal = 0
    items_validos = []
    for item in items:
        prod_result = await db.execute(select(Producto).where(Producto.id == item.get("producto_id")))
        prod = prod_result.scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=400, detail=f"Producto ID {item.get('producto_id')} no encontrado")

        # Validar funeral
        if tipo == "funeral":
            cat_lower = prod.categoria.lower()
            if not any(f in cat_lower for f in FUNERAL_CATS):
                raise HTTPException(
                    status_code=400,
                    detail=f"El producto '{prod.nombre}' no es de categoría funeral"
                )

        precio = prod.precio_descuento if (prod.precio_descuento and prod.precio_descuento < prod.precio) else prod.precio
        cantidad = item.get("cantidad", 1)
        subtotal += precio * cantidad
        items_validos.append({"producto": prod, "cantidad": cantidad, "precio": precio})

    # Buscar o crear cliente
    result = await db.execute(select(Cliente).where(Cliente.telefono == telefono))
    cliente = result.scalar_one_or_none()
    if not cliente:
        cliente = Cliente(
            nombre=nombre_cliente,
            telefono=telefono,
            email=data.get("cliente_email"),
            fuente="Web",
        )
        db.add(cliente)
        await db.flush()

    # Crear pedido
    numero = await _generar_numero_pedido(db)

    # Construir notas internas
    notas_partes = []
    if data.get("notas_entrega"):
        notas_partes.append(f"Notas repartidor: {data['notas_entrega']}")
    if tipo == "funeral":
        if data.get("nombre_fallecido"):
            notas_partes.append(f"Fallecido: {data['nombre_fallecido']}")
        if data.get("sala"):
            notas_partes.append(f"Sala: {data['sala']}")
        if data.get("banda"):
            notas_partes.append(f"Banda: {data['banda']}")
        if data.get("horario_velacion"):
            notas_partes.append(f"Velación: {data['horario_velacion']}")

    horario = data.get("horario_entrega")
    hora_exacta = None
    if horario == "hora_especifica":
        hora_exacta = data.get("hora_especifica")
        horario = "hora_exacta"

    pedido = Pedido(
        numero=numero,
        customer_id=cliente.id,
        canal="Web",
        estado="esperando_validacion",
        fecha_entrega=fecha_entrega,
        horario_entrega=horario,
        hora_exacta=hora_exacta,
        zona_entrega=None,  # Se asigna después por el florista
        direccion_entrega=data.get("direccion_entrega"),
        receptor_nombre=data.get("nombre_destinatario") if tipo == "domicilio" else nombre_cliente,
        receptor_telefono=_formatear_telefono(data.get("telefono_destinatario") or "") if tipo == "domicilio" else telefono,
        dedicatoria=data.get("dedicatoria"),
        notas_internas=" | ".join(notas_partes) if notas_partes else None,
        forma_pago=None,
        pago_confirmado=False,
        subtotal=subtotal,
        envio=0,
        total=subtotal,
        tipo_especial="Funeral" if tipo == "funeral" else ("Recoger" if tipo == "recoger" else None),
    )
    db.add(pedido)
    await db.flush()

    # Crear items
    for iv in items_validos:
        item_pedido = ItemPedido(
            pedido_id=pedido.id,
            producto_id=iv["producto"].id,
            cantidad=iv["cantidad"],
            precio_unitario=iv["precio"],
        )
        db.add(item_pedido)

    await db.commit()
    await db.refresh(pedido)

    # Enviar WhatsApp de confirmación (fire-and-forget)
    msg = (
        f"Hola {nombre_cliente.split()[0]} 🌸 Recibimos tu pedido {numero} en Florería Lucy.\n"
        f"En cuanto verifiquemos disponibilidad te contactamos con los datos para el pago.\n"
        f"¡Gracias por tu preferencia!"
    )
    try:
        await _enviar_whatsapp(telefono, msg)
    except Exception:
        pass  # No fallar si WhatsApp falla

    return {"ok": True, "folio": numero}
