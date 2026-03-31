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
from app.models.configuracion import HorarioEspecifico, CodigoDescuento, ConfiguracionNegocio
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

@router.get("/seguimiento.html", response_class=HTMLResponse)
async def seguimiento_page():
    from pathlib import Path
    html_path = Path(__file__).parent.parent / "seguimiento.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

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

@router.get("/config")
async def catalogo_config(db: AsyncSession = Depends(get_db)):
    """Config pública del catálogo — hero, textos, fecha especial."""
    result = await db.execute(select(ConfiguracionNegocio))
    cfg = {c.clave: c.valor for c in result.scalars().all()}
    return {
        "hero_imagen": cfg.get("catalogo_hero_imagen", ""),
        "hero_titulo": cfg.get("catalogo_hero_titulo", "Floreria Lucy"),
        "hero_subtitulo": cfg.get("catalogo_hero_subtitulo", "La expresion del amor"),
        "whatsapp_msg": cfg.get("catalogo_whatsapp_msg", ""),
        "footer": cfg.get("catalogo_footer", ""),
        "meta_titulo": cfg.get("catalogo_meta_titulo", "Floreria Lucy"),
        "meta_descripcion": cfg.get("catalogo_meta_descripcion", ""),
        "cerrado": cfg.get("catalogo_cerrado", "false") == "true",
        "temporada_modo": cfg.get("temporada_modo", "regular"),
        "temporada_categoria": cfg.get("temporada_categoria", ""),
        "temporada_fecha_fuerte": cfg.get("temporada_fecha_fuerte", ""),
        "temporada_dias_restriccion": int(cfg.get("temporada_dias_restriccion", "2")),
        "temporada_acepta_funerales": cfg.get("temporada_acepta_funerales", "true") == "true",
        "temporada_envio_unico": int(cfg.get("temporada_envio_unico", "9900")),
    }


@router.get("/productos")
async def catalogo_productos(
    categoria: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    # Check temporada config
    cfg_result = await db.execute(select(ConfiguracionNegocio))
    cfg = {c.clave: c.valor for c in cfg_result.scalars().all()}

    temporada_activa = False
    if cfg.get("temporada_modo") == "alta" and cfg.get("temporada_categoria"):
        fecha_str = cfg.get("temporada_fecha_fuerte", "")
        dias_restriccion = int(cfg.get("temporada_dias_restriccion", "2"))
        if fecha_str:
            try:
                fecha_fuerte = date_type.fromisoformat(fecha_str)
                from app.core.utils import hoy
                hoy_date = hoy()
                dias_diff = (fecha_fuerte - hoy_date).days
                if 0 <= dias_diff <= dias_restriccion:
                    temporada_activa = True
            except ValueError:
                pass

    query = (
        select(Producto)
        .where(
            Producto.activo == True,
            Producto.disponible_hoy == True,
            Producto.imagen_url.isnot(None),
        )
        .order_by(Producto.categoria, Producto.nombre)
    )

    if temporada_activa and not categoria:
        # Only show temporada category + funeral categories (if accepted)
        temp_cat = cfg.get("temporada_categoria", "")
        acepta_funerales = cfg.get("temporada_acepta_funerales", "true") == "true"
        if acepta_funerales:
            # Get funeral category names
            from app.models.productos import Categoria
            funeral_cats_result = await db.execute(
                select(Categoria.nombre).where(Categoria.tipo == "funeral")
            )
            funeral_names = [r[0] for r in funeral_cats_result.fetchall()]
            allowed_cats = [temp_cat] + funeral_names
            query = query.where(Producto.categoria.in_(allowed_cats))
        else:
            query = query.where(Producto.categoria == temp_cat)
    elif categoria:
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
            "sin_stock": p.stock_activo and p.stock <= 0,
        }
        for p in productos
    ]


@router.get("/catalogos-fiscales")
async def catalogos_fiscales_publico(db: AsyncSession = Depends(get_db)):
    """Catálogos de régimen fiscal y uso CFDI para formulario web."""
    from sqlalchemy import text as txt
    regs = await db.execute(txt("SELECT codigo, nombre FROM regimenes_fiscales ORDER BY codigo"))
    usos = await db.execute(txt("SELECT codigo, nombre FROM usos_cfdi ORDER BY codigo"))
    return {"regimenes": [{"codigo":r[0],"nombre":r[1]} for r in regs.fetchall()],
            "usos": [{"codigo":r[0],"nombre":r[1]} for r in usos.fetchall()]}


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
    from app.core.utils import generar_folio
    return await generar_folio(db)


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
    import traceback as _tb
    try:
        return await _crear_pedido_web_inner(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CATALOGO PEDIDO] Error: {e}\n{_tb.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def _crear_pedido_web_inner(request, db):
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

    fecha_entrega_str = data.get("fecha_entrega")
    if not fecha_entrega_str:
        raise HTTPException(status_code=400, detail="Fecha de entrega es obligatoria")
    from datetime import date as date_type
    try:
        fecha_entrega = date_type.fromisoformat(fecha_entrega_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Formato de fecha inválido")

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
        from app.core.utils import ahora
        hora_actual = ahora()
        if hora_actual.hour * 60 + hora_actual.minute >= 18 * 60 + 30:
            raise HTTPException(status_code=400, detail="Los pedidos de funeral solo se aceptan hasta las 6:30 PM")
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

    import secrets
    tracking_token = secrets.token_urlsafe(32)

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
        requiere_factura=data.get("requiere_factura", False),
        tracking_token=tracking_token,
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

    # Save datos fiscales if provided
    _df_web = data.get("datos_fiscales")
    if _df_web and data.get("requiere_factura"):
        from app.models.fiscales import DatosFiscalesCliente
        _dfc = DatosFiscalesCliente(
            cliente_id=cliente.id, rfc=_df_web.get("rfc"), razon_social=_df_web.get("razon_social"),
            regimen_fiscal=_df_web.get("regimen_fiscal"), uso_cfdi=_df_web.get("uso_cfdi"),
            correo_fiscal=_df_web.get("correo_fiscal"), codigo_postal=_df_web.get("codigo_postal"))
        db.add(_dfc)
        await db.flush()
        pedido.datos_fiscales_id = _dfc.id

    await db.commit()
    await db.refresh(pedido)

    # Enviar WhatsApp de confirmación con link de seguimiento (fire-and-forget)
    tracking_url = f"https://floreria-lucy-ecosystem-production.up.railway.app/catalogo/seguimiento.html?token={tracking_token}"
    msg = (
        f"Hola {nombre_cliente.split()[0]} 🌸 Recibimos tu pedido {numero} en Florería Lucy.\n"
        f"En cuanto verifiquemos disponibilidad te contactamos con los datos para el pago.\n\n"
        f"Sigue el estado de tu pedido aquí:\n{tracking_url}\n\n"
        f"¡Gracias por tu preferencia!"
    )
    try:
        await _enviar_whatsapp(telefono, msg)
    except Exception:
        pass  # No fallar si WhatsApp falla

    return {"ok": True, "folio": numero, "tracking_token": tracking_token}


@router.get("/seguimiento/{token}")
async def seguimiento_pedido(token: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint for customers to check order status."""
    result = await db.execute(
        select(Pedido).where(Pedido.tracking_token == token)
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Get items
    items_result = await db.execute(
        select(ItemPedido).where(ItemPedido.pedido_id == pedido.id)
    )
    items = items_result.scalars().all()
    items_data = []
    for item in items:
        prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
        prod = prod_result.scalar_one_or_none()
        items_data.append({
            "nombre": prod.nombre if prod else (item.nombre_personalizado or "Producto"),
            "cantidad": item.cantidad,
            "precio": item.precio_unitario,
            "imagen_url": prod.imagen_url if prod else None,
        })

    # Map status to customer-friendly labels
    estado_labels = {
        "esperando_validacion": {"label": "Revisando tu pedido", "desc": "Nuestro equipo está verificando disponibilidad", "icon": "🔍", "step": 1},
        "Pendiente pago": {"label": "Pedido aceptado", "desc": "Te enviaremos los datos de pago por WhatsApp", "icon": "✅", "step": 2},
        "comprobante_recibido": {"label": "Verificando pago", "desc": "Estamos revisando tu comprobante de pago", "icon": "🏦", "step": 2},
        "pagado": {"label": "Pago confirmado", "desc": "Tu arreglo será elaborado pronto", "icon": "💳", "step": 3},
        "En producción": {"label": "En elaboración", "desc": "Nuestro florista está preparando tu arreglo", "icon": "🌺", "step": 3},
        "listo_taller": {"label": "Arreglo listo", "desc": "Tu arreglo está terminado", "icon": "🎀", "step": 4},
        "En camino": {"label": "En camino", "desc": "Tu pedido va en camino a su destino", "icon": "🚗", "step": 5},
        "Entregado": {"label": "Entregado", "desc": "Tu pedido fue entregado exitosamente", "icon": "🎉", "step": 6},
        "Cancelado": {"label": "Cancelado", "desc": pedido.cancelado_razon or "Tu pedido fue cancelado", "icon": "❌", "step": 0},
    }

    estado_info = estado_labels.get(pedido.estado, {"label": pedido.estado, "desc": "", "icon": "📦", "step": 1})

    # Check if florista suggested a change
    florista_cambio = None
    if pedido.estado_florista == "cambio_sugerido" and pedido.nota_florista:
        florista_cambio = {
            "tipo": "cambio",
            "nota": pedido.nota_florista,
            "requiere_respuesta": True,
        }
    elif pedido.estado_florista == "aprobado_con_modificacion" and pedido.nota_florista:
        florista_cambio = {
            "tipo": "modificacion",
            "nota": pedido.nota_florista,
            "requiere_respuesta": True,
        }
    elif pedido.estado_florista == "rechazado":
        florista_cambio = {
            "tipo": "rechazo",
            "nota": pedido.nota_florista or "No fue posible procesar tu pedido",
            "requiere_respuesta": False,
        }

    return {
        "folio": pedido.numero,
        "estado": pedido.estado,
        "estado_label": estado_info["label"],
        "estado_desc": estado_info["desc"],
        "estado_icon": estado_info["icon"],
        "estado_step": estado_info["step"],
        "fecha_entrega": str(pedido.fecha_entrega) if pedido.fecha_entrega else None,
        "horario_entrega": pedido.horario_entrega,
        "items": items_data,
        "subtotal": pedido.subtotal,
        "total": pedido.total,
        "florista_cambio": florista_cambio,
        "created_at": str(pedido.fecha_pedido) if pedido.fecha_pedido else None,
    }


@router.post("/seguimiento/{token}/responder")
async def responder_seguimiento(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Customer responds to florista's change suggestion."""
    result = await db.execute(
        select(Pedido).where(Pedido.tracking_token == token)
    )
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if pedido.estado_florista not in ("cambio_sugerido", "aprobado_con_modificacion"):
        raise HTTPException(status_code=400, detail="No hay cambio pendiente de respuesta")

    data = await request.json()
    acepta = data.get("acepta", False)
    mensaje = (data.get("mensaje") or "").strip()

    if acepta:
        pedido.estado_florista = "pendiente_aprobacion"
        nota_respuesta = f"[CLIENTE ACEPTA CAMBIO] {mensaje}" if mensaje else "[CLIENTE ACEPTA CAMBIO]"
    else:
        pedido.estado_florista = "requiere_atencion"
        pedido.requiere_humano = True
        nota_respuesta = f"[CLIENTE RECHAZA CAMBIO] {mensaje}" if mensaje else "[CLIENTE RECHAZA CAMBIO]"

    # Append to notas_internas
    if pedido.notas_internas:
        pedido.notas_internas += f" | {nota_respuesta}"
    else:
        pedido.notas_internas = nota_respuesta

    await db.commit()
    return {"ok": True, "nuevo_estado": pedido.estado_florista}
