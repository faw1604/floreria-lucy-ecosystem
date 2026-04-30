from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import os, logging, httpx, json
from app.core.limiter import limiter
from app.database import get_db
from app.models.productos import Producto, ProductoVariante
from app.models.pedidos import Pedido, ItemPedido
from app.models.clientes import Cliente
from app.models.configuracion import HorarioEspecifico, CodigoDescuento, ConfiguracionNegocio
from app.core.config import TZ
from app.core.estados import EstadoPedido as EP, EstadoFlorista as EF
from app.core.utils import limpiar_telefono
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

@router.get("/producto.html")
async def producto_page(id: int | None = None, db: AsyncSession = Depends(get_db)):
    """
    Sirve producto.html con SEO meta inyectado server-side cuando hay ?id=X.
    Esto permite que Google bot vea title/description/og/JSON-LD del producto
    real, en lugar del HTML genérico que carga todo via JS.
    El cliente (browser) sigue funcionando igual: el JS sobreescribe lo que
    necesite tras el fetch a /catalogo/producto/{id}.
    """
    from pathlib import Path
    import html as _html
    import json as _json
    html_path = Path(__file__).parent.parent / "producto.html"
    raw = html_path.read_text(encoding="utf-8")

    # Si no hay id, servir HTML original (la JS mostrará error "Producto no especificado")
    if not id:
        return HTMLResponse(raw)

    try:
        prod = (await db.execute(select(Producto).where(Producto.id == id))).scalar_one_or_none()
        # Solo inyectar SEO si producto existe y es visible al público
        if not prod or not prod.activo or not prod.visible_catalogo:
            return HTMLResponse(raw)

        nombre = prod.nombre or "Producto"
        descripcion_raw = (prod.descripcion or f"{nombre} — Floreria Lucy, arreglos florales en Chihuahua").strip()
        # Limpiar saltos de linea y limitar a 160 chars para meta description
        descripcion = " ".join(descripcion_raw.split())[:160]
        precio_centavos = prod.precio_descuento if (prod.precio_descuento and prod.precio_descuento < prod.precio) else prod.precio
        precio_mxn = f"{precio_centavos / 100:.2f}"
        imagen = prod.imagen_url or "https://res.cloudinary.com/ddku2wmpk/image/upload/v1774476982/floreria-lucy/hero.jpg"
        url_canonica = f"https://www.florerialucy.com/catalogo/producto.html?id={id}"

        # Disponibilidad: si stock_activo y stock<=0 => OutOfStock
        sin_stock = bool(prod.stock_activo and prod.stock <= 0)
        availability = "https://schema.org/OutOfStock" if sin_stock else "https://schema.org/InStock"

        # Seller enriquecido (reusable en Product.offers)
        seller_completo = {
            "@type": "Florist",
            "name": "Florería Lucy",
            "url": "https://www.florerialucy.com/",
            "telephone": "+52-614-414-3787",
            "priceRange": "$$",
            "image": "https://res.cloudinary.com/ddku2wmpk/image/upload/v1775163240/floreria-lucy/logo.png",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "C. Sabino 610, Las Granjas",
                "addressLocality": "Chihuahua",
                "addressRegion": "Chihuahua",
                "postalCode": "31100",
                "addressCountry": "MX"
            }
        }

        # JSON-LD Product
        product_jsonld = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": nombre,
            "description": descripcion,
            "image": imagen,
            "category": prod.categoria,
            "sku": f"FL-{prod.id}",
            "brand": {"@type": "Brand", "name": "Florería Lucy"},
            "offers": {
                "@type": "Offer",
                "url": url_canonica,
                "priceCurrency": "MXN",
                "price": precio_mxn,
                "availability": availability,
                "itemCondition": "https://schema.org/NewCondition",
                "seller": seller_completo,
                "shippingDetails": {
                    "@type": "OfferShippingDetails",
                    "shippingRate": {
                        "@type": "MonetaryAmount",
                        "minValue": "79.00",
                        "maxValue": "199.00",
                        "currency": "MXN"
                    },
                    "shippingDestination": {
                        "@type": "DefinedRegion",
                        "addressCountry": "MX",
                        "addressRegion": "Chihuahua"
                    },
                    "deliveryTime": {
                        "@type": "ShippingDeliveryTime",
                        "handlingTime": {
                            "@type": "QuantitativeValue",
                            "minValue": 0,
                            "maxValue": 1,
                            "unitCode": "DAY"
                        },
                        "transitTime": {
                            "@type": "QuantitativeValue",
                            "minValue": 0,
                            "maxValue": 1,
                            "unitCode": "DAY"
                        }
                    }
                },
                "hasMerchantReturnPolicy": {
                    "@type": "MerchantReturnPolicy",
                    "applicableCountry": "MX",
                    "returnPolicyCategory": "https://schema.org/MerchantReturnNotPermitted"
                }
            }
        }

        # Escapar valores para meta tags
        nombre_esc = _html.escape(nombre, quote=True)
        desc_esc = _html.escape(descripcion, quote=True)
        cat_esc = _html.escape(prod.categoria or "", quote=True)
        imagen_esc = _html.escape(imagen, quote=True)

        seo_block = f"""<title>{nombre_esc} — Florería Lucy</title>
<meta name="description" content="{desc_esc}">

<!-- SEO -->
<link rel="canonical" href="{url_canonica}">
<meta name="robots" content="index, follow">
<meta name="geo.region" content="MX-CHH">
<meta name="geo.placename" content="Chihuahua">

<!-- Open Graph (product) -->
<meta property="og:type" content="product">
<meta property="og:site_name" content="Floreria Lucy">
<meta property="og:title" content="{nombre_esc} — Florería Lucy">
<meta property="og:description" content="{desc_esc}">
<meta property="og:url" content="{url_canonica}">
<meta property="og:locale" content="es_MX">
<meta property="og:image" content="{imagen_esc}">
<meta property="og:image:alt" content="{nombre_esc}">
<meta property="product:price:amount" content="{precio_mxn}">
<meta property="product:price:currency" content="MXN">
<meta property="product:category" content="{cat_esc}">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{nombre_esc} — Florería Lucy">
<meta name="twitter:description" content="{desc_esc}">
<meta name="twitter:image" content="{imagen_esc}">

<!-- Schema.org: Product -->
<script type="application/ld+json">
{_json.dumps(product_jsonld, ensure_ascii=False)}
</script>

<!-- Schema.org: BreadcrumbList -->
<script type="application/ld+json">
{_json.dumps({
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Inicio", "item": "https://www.florerialucy.com/"},
        {"@type": "ListItem", "position": 2, "name": "Catálogo", "item": "https://www.florerialucy.com/catalogo/"},
        {"@type": "ListItem", "position": 3, "name": nombre, "item": url_canonica}
    ]
}, ensure_ascii=False)}
</script>

<link rel="icon" type="image/png" href="https://res.cloudinary.com/ddku2wmpk/image/upload/w_32,h_32,c_fit,q_auto/v1775163240/floreria-lucy/logo.png">
<link rel="apple-touch-icon" href="https://res.cloudinary.com/ddku2wmpk/image/upload/w_180,h_180,c_fit,q_auto/v1775163240/floreria-lucy/logo.png">"""

        # Reemplazar el title genérico con el bloque SEO completo
        html_con_seo = raw.replace("<title>Florería Lucy</title>", seo_block, 1)
        return HTMLResponse(html_con_seo)

    except Exception as e:
        logger.error(f"[SEO producto SSR] Error inyectando meta para id={id}: {e}")
        # Fallback: HTML original. El cliente sigue funcionando vía JS.
        return HTMLResponse(raw)

@router.get("/historia")
async def historia_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/historia", status_code=301)

@router.get("/contacto")
async def contacto_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/contacto", status_code=301)

@router.get("/facturacion")
async def facturacion_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/facturacion", status_code=301)

@router.get("/legal")
async def legal_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/legal", status_code=301)

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
        "temporada_nombre": cfg.get("temporada_nombre", ""),
        "temporada_categoria": cfg.get("temporada_categoria", ""),
        "temporada_fecha_fuerte": cfg.get("temporada_fecha_fuerte", ""),
        "temporada_dias_restriccion": int(cfg.get("temporada_dias_restriccion", "2")),
        "temporada_acepta_funerales": cfg.get("temporada_acepta_funerales", "true") == "true",
        "temporada_envio_unico": int(cfg.get("temporada_envio_unico", "9900")),
        "temporada_horario_apertura": cfg.get("temporada_horario_apertura", ""),
        "temporada_horario_cierre": cfg.get("temporada_horario_cierre", ""),
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
            Producto.visible_catalogo == True,
            Producto.imagen_url.isnot(None),
            Producto.vender_por_fraccion == False,  # productos por fracción son solo POS
        )
        .order_by(Producto.destacado.desc(), Producto.categoria, Producto.nombre)
    )

    if temporada_activa and not categoria:
        # Mostrar: categoría temporada + categorías de regalos + funeral (si está activo)
        temp_cat = cfg.get("temporada_categoria", "")
        acepta_funerales = cfg.get("temporada_acepta_funerales", "true") == "true"
        # Categorías tipo "regalo" (deben coincidir con REGALOS_CATS de catalogo.html)
        regalos_cats_lower = ["chocolates gourmet", "peluches", "globos", "dulces y regalos", "extras", "regalos"]
        allowed_lower = [temp_cat.lower()] + regalos_cats_lower
        if acepta_funerales:
            from app.models.productos import Categoria
            funeral_cats_result = await db.execute(
                select(Categoria.nombre).where(Categoria.tipo == "funeral")
            )
            allowed_lower += [r[0].lower() for r in funeral_cats_result.fetchall()]
        query = query.where(func.lower(Producto.categoria).in_(allowed_lower))
    elif categoria:
        query = query.where(Producto.categoria == categoria)

    result = await db.execute(query)
    productos = result.scalars().all()

    # Cargar variantes activas de todos los productos de una vez
    prod_ids = [p.id for p in productos]
    variantes_map = {}
    if prod_ids:
        vars_result = await db.execute(
            select(ProductoVariante)
            .where(ProductoVariante.producto_id.in_(prod_ids), ProductoVariante.activo == True)
            .order_by(ProductoVariante.tipo, ProductoVariante.nombre)
        )
        for v in vars_result.scalars().all():
            variantes_map.setdefault(v.producto_id, []).append({
                "id": v.id, "tipo": v.tipo, "nombre": v.nombre,
                "precio": v.precio, "imagen_url": v.imagen_url,
            })

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
            "imagenes_extra": json.loads(p.imagenes_extra) if p.imagenes_extra else [],
            "disponible_hoy": p.disponible_hoy,
            "etiquetas": p.etiquetas,
            "dimensiones": p.dimensiones,
            "medida_alto": float(p.medida_alto) if p.medida_alto else None,
            "medida_ancho": float(p.medida_ancho) if p.medida_ancho else None,
            "sin_stock": p.stock_activo and p.stock <= 0,
            "destacado": p.destacado,
            "variantes": variantes_map.get(p.id, []),
        }
        for p in productos
    ]


@router.get("/producto/{producto_id}")
async def catalogo_producto_detalle(producto_id: int, db: AsyncSession = Depends(get_db)):
    """Public endpoint for single product detail (shareable link)."""
    result = await db.execute(
        select(Producto).where(Producto.id == producto_id, Producto.activo == True)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    # Cargar variantes activas
    vres = await db.execute(
        select(ProductoVariante)
        .where(ProductoVariante.producto_id == producto_id, ProductoVariante.activo == True)
        .order_by(ProductoVariante.tipo, ProductoVariante.id)
    )
    variantes = [
        {
            "id": v.id,
            "tipo": v.tipo,
            "nombre": v.nombre,
            "codigo": v.codigo,
            "imagen_url": v.imagen_url,
            "precio": v.precio,
            "precio_descuento": v.precio_descuento,
            "stock_activo": v.stock_activo,
            "stock": v.stock,
        }
        for v in vres.scalars().all()
    ]
    return {
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
        "imagenes_extra": json.loads(p.imagenes_extra) if p.imagenes_extra else [],
        "etiquetas": p.etiquetas,
        "dimensiones": p.dimensiones,
        "medida_alto": float(p.medida_alto) if p.medida_alto else None,
        "medida_ancho": float(p.medida_ancho) if p.medida_ancho else None,
        "sin_stock": p.stock_activo and p.stock <= 0,
        "destacado": p.destacado,
        "variantes": variantes,
    }


@router.get("/zonas-envio")
async def zonas_envio_publico(db: AsyncSession = Depends(get_db)):
    """Lista zonas de envío con tarifa efectiva (override admin o base GeoJSON).
    Usado por POS para popular dropdown de zonas. Solo devuelve zonas activas."""
    from app.services.zonas_envio import listar_zonas_efectivas
    zonas = await listar_zonas_efectivas(db)
    return [z for z in zonas if z["activa"]]


@router.get("/turnos-activos")
async def turnos_activos_publico(db: AsyncSession = Depends(get_db)):
    """Devuelve qué turnos de entrega están activos (admin puede desactivar
    temporalmente: 'hoy ya no acepto noche', vacaciones, etc.).
    Usado por Web y POS para ocultar opciones de horario apagadas."""
    from sqlalchemy import text as txt
    r = await db.execute(txt(
        "SELECT clave, valor FROM configuracion_negocio "
        "WHERE clave IN ('turno_manana_activo','turno_tarde_activo',"
        "'turno_noche_activo','turno_recoger_activo')"
    ))
    cfg = {row[0]: row[1] for row in r.fetchall()}
    return {
        "manana": cfg.get("turno_manana_activo", "true") == "true",
        "tarde": cfg.get("turno_tarde_activo", "true") == "true",
        "noche": cfg.get("turno_noche_activo", "true") == "true",
        "recoger": cfg.get("turno_recoger_activo", "true") == "true",
    }


@router.get("/capacidad-turnos")
async def capacidad_turnos(fecha: str, db: AsyncSession = Depends(get_db)):
    """Devuelve capacidad y agendados de Turno 1 (mañana) y Turno 2 (tarde)
    para una fecha dada. Solo aplica a entrega a DOMICILIO en la fecha fuerte
    de temporada alta. Si la fecha no es la fecha fuerte o el cap está
    desactivado, devuelve cap=null (frontend lo ignora).

    'Agendados' cuenta TODOS los pedidos no cancelados (incluye
    esperando_validacion y pendiente_pago) para reservar el slot incluso si
    aún no han pagado — evita prometer el mismo turno a 2 clientes.
    """
    from sqlalchemy import text as txt
    try:
        fecha_d = date_type.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="fecha inválida (YYYY-MM-DD)")

    r = await db.execute(select(ConfiguracionNegocio))
    cfg = {c.clave: c.valor for c in r.scalars().all()}

    cap_activo = (cfg.get("temporada_cap_activo", "false") == "true")
    fecha_fuerte_str = cfg.get("temporada_fecha_fuerte", "")
    if not cap_activo or not fecha_fuerte_str:
        return {"activo": False, "turno1": None, "turno2": None}
    try:
        fecha_fuerte = date_type.fromisoformat(fecha_fuerte_str)
    except ValueError:
        return {"activo": False, "turno1": None, "turno2": None}
    if fecha_d != fecha_fuerte:
        return {"activo": False, "turno1": None, "turno2": None}

    cap_t1 = int(cfg.get("temporada_cap_turno1", "0") or "0")
    cap_t2 = int(cfg.get("temporada_cap_turno2", "0") or "0")
    cap_recoger = int(cfg.get("temporada_cap_recoger", "0") or "0")

    # Contar pedidos a domicilio agendados para esa fecha por turno.
    # Solo excluimos cancelados/rechazados (decisión 4B): incluye esperando_validacion
    # y pendiente_pago para reservar el slot aunque aún no haya pagado.
    res = await db.execute(
        txt("SELECT horario_entrega, COUNT(*) FROM pedidos "
            "WHERE fecha_entrega = :f "
            "AND estado NOT IN ('Cancelado','rechazado') "
            "AND metodo_entrega IN ('envio','funeral_envio','domicilio') "
            "GROUP BY horario_entrega"),
        {"f": fecha_d}
    )
    counts = {row[0]: row[1] for row in res.fetchall()}
    # Mapeo de horario_entrega → turno: 'manana'/'mañana' = T1, 'tarde' = T2
    ag_t1 = counts.get("manana", 0) + counts.get("mañana", 0)
    ag_t2 = counts.get("tarde", 0)

    # Contar pedidos para recoger en tienda esa fecha (cualquier hora del día).
    res_rec = await db.execute(
        txt("SELECT COUNT(*) FROM pedidos "
            "WHERE fecha_entrega = :f "
            "AND estado NOT IN ('Cancelado','rechazado') "
            "AND metodo_entrega = 'recoger'"),
        {"f": fecha_d}
    )
    ag_recoger = res_rec.scalar() or 0

    def _info(cap, ag):
        if cap <= 0:
            return None  # Sin cap configurado
        return {
            "cap": cap,
            "agendados": ag,
            "lleno": ag >= cap,
            "ultimos_cupos": ag >= int(cap * 0.9) and ag < cap,
        }

    return {
        "activo": True,
        "fecha": fecha,
        "turno1": _info(cap_t1, ag_t1),
        "turno2": _info(cap_t2, ag_t2),
        "recoger": _info(cap_recoger, ag_recoger),
    }


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


@router.get("/direccion/autocomplete")
@limiter.limit("30/minute")
async def catalogo_autocomplete(request: Request, q: str = ""):
    """Sugerencias de direcciones (público, rate limited)."""
    if len(q) < 3:
        return {"suggestions": []}
    from app.services.geocoding import autocomplete
    return {"suggestions": await autocomplete(q)}


@router.post("/direccion/seleccionar")
@limiter.limit("10/minute")
async def catalogo_seleccionar(request: Request, db: AsyncSession = Depends(get_db)):
    """Obtiene coordenadas de un place_id y asigna zona."""
    data = await request.json()
    place_id = data.get("place_id", "")
    from app.services.geocoding import place_details
    from app.services.zonas_envio import obtener_zona_envio_db

    if place_id:
        result = await place_details(place_id)
    else:
        from app.services.geocoding import geocodificar
        result = await geocodificar(data.get("direccion", ""))

    if not result:
        return {"error": "No se pudo obtener la ubicación"}

    lat, lng = result["lat"], result["lng"]
    zona = await obtener_zona_envio_db(db, lat, lng)
    return {
        "lat": lat, "lng": lng,
        "zona_envio": zona["zona"] if zona else None,
        "tarifa_envio": zona["tarifa"] * 100 if zona else None,
        "fuera_de_cobertura": zona is None,
        "display_name": result["display_name"],
    }


@router.post("/carrito-compartido")
async def crear_carrito_compartido(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Crea un carrito compartido desde POS y devuelve código corto."""
    from app.models.pedidos import CarritoCompartido
    import secrets
    data = await request.json()
    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")
    codigo = secrets.token_urlsafe(6)[:8]
    carrito = CarritoCompartido(codigo=codigo, items_json=json.dumps(items))
    db.add(carrito)
    await db.commit()
    return {"ok": True, "codigo": codigo, "url": f"https://www.florerialucy.com/catalogo?carrito={codigo}"}


@router.get("/carrito-compartido/{codigo}")
async def obtener_carrito_compartido(
    codigo: str,
    db: AsyncSession = Depends(get_db),
):
    """Devuelve los items de un carrito compartido."""
    from app.models.pedidos import CarritoCompartido
    result = await db.execute(select(CarritoCompartido).where(CarritoCompartido.codigo == codigo))
    carrito = result.scalar_one_or_none()
    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    return {"items": json.loads(carrito.items_json), "codigo": carrito.codigo}


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


def _dedicatoria_funeral(dedicatoria: str | None, fallecido: str | None) -> str | None:
    """Combina dedicatoria + nombre del fallecido con cruz."""
    partes = []
    if dedicatoria and dedicatoria.strip():
        partes.append(dedicatoria.strip())
    if fallecido and fallecido.strip():
        partes.append(f"† {fallecido.strip()}")
    return "\n".join(partes) if partes else None


def _formatear_telefono(tel: str) -> str:
    """Normaliza teléfono a 10 dígitos (sin prefijo 52/521).

    Wrapper local para mantener la firma; la lógica vive en core/utils.limpiar_telefono.
    """
    return limpiar_telefono(tel)


async def _enviar_whatsapp(telefono: str, mensaje: str):
    """Envía mensaje WhatsApp directo a Whapi. Fallback a proxy agentkit si falla."""
    # Normalizar a solo dígitos, formato 521XXXXXXXXXX para México
    digitos = "".join(c for c in telefono if c.isdigit())
    if len(digitos) == 10:
        digitos = "521" + digitos
    elif len(digitos) == 12 and digitos.startswith("52"):
        # 52 + 10 dígitos sin el 1 → agregar
        digitos = "521" + digitos[2:]
    elif not digitos.startswith("52") and len(digitos) <= 10:
        digitos = "521" + digitos

    whapi_token = os.environ.get("WHAPI_TOKEN")
    if whapi_token:
        # Intento directo a Whapi (mismo método que POS)
        logger.info(f"[WHAPI] Enviando directo a {digitos}")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://gate.whapi.cloud/messages/text",
                    headers={"Authorization": f"Bearer {whapi_token}", "Content-Type": "application/json"},
                    json={"to": digitos, "body": mensaje},
                )
            if r.status_code in (200, 201):
                logger.info(f"[WHAPI] WhatsApp enviado directo OK — {r.status_code}")
                return
            else:
                logger.error(f"[WHAPI] Error directo {r.status_code}: {r.text[:300]}")
        except Exception as e:
            logger.error(f"[WHAPI] Error directo: {type(e).__name__}: {e}")
    else:
        logger.warning("[WHAPI] WHAPI_TOKEN no configurado, intentando proxy")

    # Fallback: proxy via agentkit
    agentkit_url = os.getenv("AGENTKIT_URL", "https://whatsapp-agentkit-production-4e69.up.railway.app")
    agentkit_key = os.getenv("AGENTKIT_API_KEY", "")
    logger.info(f"[WHAPI] Fallback proxy agentkit a {digitos}")
    try:
        headers = {"Content-Type": "application/json"}
        if agentkit_key:
            headers["X-Admin-Key"] = agentkit_key
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{agentkit_url}/enviar-mensaje-claudia",
                headers=headers,
                json={"telefono": digitos, "mensaje": mensaje},
            )
        if r.status_code >= 400:
            logger.error(f"[WHAPI] Error proxy {r.status_code}: {r.text[:300]}")
        else:
            logger.info(f"[WHAPI] WhatsApp enviado via proxy — {r.status_code}")
    except Exception as e:
        logger.error(f"[WHAPI] Error proxy: {type(e).__name__}: {e}")


@router.post("/pedido")
@limiter.limit("10/minute")
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
        raise HTTPException(status_code=500, detail="Error interno al procesar pedido")

async def _crear_pedido_web_inner(request, db):
    data = await request.json()

    tipo = data.get("tipo", "domicilio")
    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Debes agregar al menos un producto")

    # Validar método de pago (web acepta Transferencia, OXXO y Link de pago/MP)
    forma_pago = data.get("forma_pago")
    if forma_pago not in ("Transferencia", "OXXO", "Link de pago"):
        raise HTTPException(status_code=400, detail="Método de pago inválido. Selecciona Transferencia, OXXO o Tarjeta.")

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

    # Bloquear fechas pasadas (defensa contra picker iOS o frontend desactualizado)
    from app.core.utils import hoy as hoy_chihuahua
    hoy_date = hoy_chihuahua()
    if fecha_entrega < hoy_date:
        raise HTTPException(status_code=400, detail="La fecha de entrega ya pasó. Selecciona una fecha válida.")

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
        # Límite: 30 min antes del cierre (Lun-Vie 18:30, Sáb 17:30, Dom 14:30)
        dia = hora_actual.weekday()  # 0=Lun, 6=Dom
        limites = {6: 14*60+30, 5: 17*60+30}  # Dom, Sáb
        limite_min = limites.get(dia, 18*60+30)  # default Lun-Vie
        if hora_actual.hour * 60 + hora_actual.minute >= limite_min:
            raise HTTPException(status_code=400, detail="Ya pasó el horario límite para pedidos funeral de hoy")
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

        # Validar stock
        cantidad = item.get("cantidad", 1)
        if prod.stock_activo and prod.stock < cantidad:
            raise HTTPException(
                status_code=400,
                detail=f"'{prod.nombre}' no tiene stock suficiente (disponible: {prod.stock})"
            )

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

        # Variante: validar si viene y aplicar precio
        variante_id = item.get("variante_id")
        variante_nombre = None
        if variante_id:
            var_r = await db.execute(select(ProductoVariante).where(
                ProductoVariante.id == variante_id,
                ProductoVariante.producto_id == prod.id,
                ProductoVariante.activo == True,
            ))
            variante = var_r.scalar_one_or_none()
            if not variante:
                raise HTTPException(status_code=400, detail=f"Variante no válida para '{prod.nombre}'")
            variante_nombre = variante.nombre
            if variante.precio and variante.precio > 0:
                precio = variante.precio

        subtotal += precio * cantidad
        items_validos.append({"producto": prod, "cantidad": cantidad, "precio": precio,
                              "variante_id": variante_id, "variante_nombre": variante_nombre,
                              "bandas": item.get("bandas")})

    # IVA: si requiere factura, 16% sobre productos no-chocolate
    impuesto = 0
    if data.get("requiere_factura"):
        sub_flores = sum(
            iv["precio"] * iv["cantidad"]
            for iv in items_validos
            if "chocolates gourmet" not in (iv["producto"].categoria or "").lower()
        )
        impuesto = int(sub_flores * 0.16)

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

    # Calcular envío
    envio = 0
    zona_entrega_val = None
    funeraria_nombre = None
    funeraria_zona = None

    # Domicilio: zona y tarifa del autocomplete
    if tipo == "domicilio":
        zona_entrega_val = data.get("zona_entrega")
        # SIEMPRE consultar tarifa actual del backend (respeta overrides admin)
        # No confiar en costo_envio enviado por el cliente — podría estar manipulado o viejo
        if zona_entrega_val:
            from app.services.zonas_envio import tarifa_zona_centavos
            envio = await tarifa_zona_centavos(db, zona_entrega_val)
    if tipo == "funeral":
        funeraria_id = data.get("funeraria_id")
        if funeraria_id:
            from app.models.funerarias import Funeraria
            fun_r = await db.execute(select(Funeraria).where(Funeraria.id == funeraria_id))
            fun = fun_r.scalar_one_or_none()
            if fun:
                envio = fun.costo_envio or 0
                funeraria_nombre = fun.nombre
                funeraria_zona = fun.zona
        elif data.get("funeral_domicilio"):
            # Funeral en domicilio particular
            envio = int(data.get("funeral_domicilio_costo", 0))
            funeraria_nombre = "Domicilio particular"
            funeraria_zona = (data.get("funeral_domicilio_zona") or "").title()

    # Construir notas internas
    notas_partes = []
    if data.get("notas_entrega"):
        notas_partes.append(f"Notas repartidor: {data['notas_entrega']}")
    if tipo == "funeral":
        if funeraria_nombre:
            notas_partes.append(f"Funeraria: {funeraria_nombre}")
        if data.get("funeral_domicilio") and data.get("funeral_direccion"):
            notas_partes.append(f"Direccion: {data['funeral_direccion']}")
            if data.get("funeral_referencias"):
                notas_partes.append(f"Ref: {data['funeral_referencias']}")
        if data.get("nombre_fallecido"):
            notas_partes.append(f"Fallecido: {data['nombre_fallecido']}")
        if data.get("sala"):
            notas_partes.append(f"Sala: {data['sala']}")
        if data.get("banda"):
            notas_partes.append(f"Banda: {data['banda']}")
        if data.get("horario_velacion"):
            notas_partes.append(f"Velación: {data['horario_velacion']}")
        # Bandas extra (con costo)
        bandas_extra_str = data.get("bandas_extra")
        if bandas_extra_str:
            notas_partes.append(f"Bandas extra: {bandas_extra_str}")

    horario = data.get("horario_entrega")
    hora_exacta = None
    if horario == "hora_especifica" or tipo == "recoger":
        hora_exacta = data.get("hora_especifica")
        if hora_exacta:
            horario = "hora_exacta"

    import secrets
    tracking_token = secrets.token_urlsafe(32)

    # --- Fecha fuerte de temporada: saltar aprobación taller ---
    es_fecha_fuerte = False
    cfg_result2 = await db.execute(select(ConfiguracionNegocio))
    cfg = {c.clave: c.valor for c in cfg_result2.scalars().all()}
    if cfg.get("temporada_modo") == "alta" and cfg.get("temporada_fecha_fuerte"):
        try:
            fecha_fuerte = date_type.fromisoformat(cfg["temporada_fecha_fuerte"])
            dias_restr = int(cfg.get("temporada_dias_restriccion", "2"))
            diff = (fecha_fuerte - fecha_entrega).days
            if 0 <= diff < dias_restr:
                es_fecha_fuerte = True
        except Exception:
            pass

    # --- Validación servidor: capacidad por turno/recoger (anti race condition con frontend) ---
    # Aplica para fecha fuerte exacta + cap activo. Distingue domicilio (turnos) vs recoger.
    if (cfg.get("temporada_cap_activo", "false") == "true"
            and cfg.get("temporada_fecha_fuerte")):
        try:
            ff = date_type.fromisoformat(cfg["temporada_fecha_fuerte"])
            if fecha_entrega == ff:
                from sqlalchemy import text as _txt
                # Caso 1: domicilio en turno 1/2
                if horario in ("turno1", "turno2") and tipo in ("envio", "domicilio", "funeral_envio"):
                    cap_key = "temporada_cap_turno1" if horario == "turno1" else "temporada_cap_turno2"
                    cap = int(cfg.get(cap_key, "0") or "0")
                    if cap > 0:
                        horarios_match = ("manana", "mañana") if horario == "turno1" else ("tarde",)
                        res = await db.execute(_txt(
                            "SELECT COUNT(*) FROM pedidos WHERE fecha_entrega = :f "
                            "AND estado NOT IN ('Cancelado','rechazado') "
                            "AND metodo_entrega IN ('envio','funeral_envio','domicilio') "
                            "AND horario_entrega = ANY(:hs)"
                        ), {"f": fecha_entrega, "hs": list(horarios_match)})
                        agendados = res.scalar() or 0
                        if agendados >= cap:
                            nombre_t = "Turno 1 (mañana)" if horario == "turno1" else "Turno 2 (tarde)"
                            raise HTTPException(
                                status_code=409,
                                detail=f"{nombre_t} está lleno para esa fecha. Por favor elige otro turno."
                            )
                # Caso 2: recoger en tienda (cualquier hora del día)
                elif tipo == "recoger":
                    cap_rec = int(cfg.get("temporada_cap_recoger", "0") or "0")
                    if cap_rec > 0:
                        res = await db.execute(_txt(
                            "SELECT COUNT(*) FROM pedidos WHERE fecha_entrega = :f "
                            "AND estado NOT IN ('Cancelado','rechazado') "
                            "AND metodo_entrega = 'recoger'"
                        ), {"f": fecha_entrega})
                        agendados = res.scalar() or 0
                        if agendados >= cap_rec:
                            raise HTTPException(
                                status_code=409,
                                detail="Ya no aceptamos más pedidos para recoger en tienda esa fecha. Por favor elige otra fecha o entrega a domicilio."
                            )
        except HTTPException:
            raise
        except Exception:
            # No bloquear creación de pedido por error de validación de cap
            pass

    # --- Restricción de categorías en fecha fuerte ---
    if es_fecha_fuerte and tipo != "funeral":
        # Categorías regalos (deben coincidir con REGALOS_CATS de catalogo.html y listado)
        cats_permitidas = [
            (cfg.get("temporada_categoria") or "").lower(),
            "chocolates gourmet", "peluches", "globos", "dulces y regalos", "extras", "regalos",
        ]
        if cfg.get("temporada_acepta_funerales", "true") == "true":
            cats_permitidas.extend(FUNERAL_CATS)
        for item_data in items_validos:
            prod = item_data["producto"]
            cat = (prod.categoria or "").lower()
            if not any(cp in cat for cp in cats_permitidas):
                raise HTTPException(
                    status_code=400,
                    detail=f"'{prod.nombre}' no está disponible para la fecha seleccionada. Solo productos de temporada y regalos."
                )

    if es_fecha_fuerte:
        estado_inicial = EP.PENDIENTE_PAGO
        estado_florista_inicial = EF.APROBADO
    else:
        estado_inicial = EP.ESPERANDO_VALIDACION
        estado_florista_inicial = None

    pedido = Pedido(
        numero=numero,
        customer_id=cliente.id,
        canal="Web",
        estado=estado_inicial,
        fecha_entrega=fecha_entrega,
        horario_entrega=horario,
        hora_exacta=hora_exacta,
        zona_entrega=funeraria_zona if tipo == "funeral" else zona_entrega_val,
        direccion_entrega=data.get("funeral_direccion") if (tipo == "funeral" and data.get("funeral_domicilio")) else data.get("direccion_entrega"),
        receptor_nombre=data.get("nombre_destinatario") if tipo == "domicilio" else nombre_cliente,
        receptor_telefono=_formatear_telefono(data.get("telefono_destinatario") or "") if tipo == "domicilio" else telefono,
        dedicatoria=_dedicatoria_funeral(data.get("dedicatoria"), data.get("nombre_fallecido")) if tipo == "funeral" else data.get("dedicatoria"),
        notas_internas=" | ".join(notas_partes) if notas_partes else None,
        forma_pago=data.get("forma_pago"),
        pago_confirmado=False,
        subtotal=subtotal + (int(data.get("bandas_extra_costo", 0)) if tipo == "funeral" else 0),
        envio=envio,
        total=subtotal + impuesto + envio + (int(data.get("bandas_extra_costo", 0)) if tipo == "funeral" else 0),
        tipo_especial="Funeral" if tipo == "funeral" else ("Recoger" if tipo == "recoger" else None),
        metodo_entrega="funeral_envio" if tipo == "funeral" else ("recoger" if tipo == "recoger" else "envio"),
        requiere_factura=data.get("requiere_factura", False),
        tracking_token=tracking_token,
        estado_florista=estado_florista_inicial,
    )
    db.add(pedido)
    await db.flush()

    # Crear items
    for iv in items_validos:
        # Construir observaciones con bandas: "Banda: TEXTO" o "U1-B1: TEXTO | U1-B2: TEXTO | U2-B1: TEXTO"
        observaciones = None
        bandas_item = iv.get("bandas")
        if bandas_item and isinstance(bandas_item, list):
            partes = []
            for u_idx, unidad_bandas in enumerate(bandas_item):
                if not unidad_bandas:
                    continue
                for b_idx, banda_texto in enumerate(unidad_bandas):
                    if not banda_texto:
                        continue
                    if iv["cantidad"] > 1 and len(unidad_bandas) > 1:
                        partes.append(f"U{u_idx+1}-B{b_idx+1}: {banda_texto}")
                    elif iv["cantidad"] > 1:
                        partes.append(f"U{u_idx+1}: {banda_texto}")
                    elif len(unidad_bandas) > 1:
                        partes.append(f"Banda {b_idx+1}: {banda_texto}")
                    else:
                        partes.append(f"Banda: {banda_texto}")
            if partes:
                observaciones = " | ".join(partes)
        item_pedido = ItemPedido(
            pedido_id=pedido.id,
            producto_id=iv["producto"].id,
            cantidad=iv["cantidad"],
            precio_unitario=iv["precio"],
            variante_id=iv.get("variante_id"),
            variante_nombre=iv.get("variante_nombre"),
            observaciones=observaciones,
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

    # Enviar WhatsApp de confirmación (solo para pedidos web, no Claudia)
    if not data.get("skip_whatsapp"):
        tracking_url = f"https://www.florerialucy.com/catalogo/seguimiento.html?token={tracking_token}"
        if es_fecha_fuerte:
            msg = (
                f"Hola {nombre_cliente.split()[0]} 🌸 Tu pedido {numero} ha sido confirmado en Florería Lucy.\n"
                f"En breve te enviaremos los datos para realizar tu pago.\n\n"
                f"Sigue el estado de tu pedido aquí:\n{tracking_url}\n\n"
                f"¡Gracias por tu preferencia!"
            )
        else:
            msg = (
                f"Hola {nombre_cliente.split()[0]} 🌸 Recibimos tu pedido {numero} en Florería Lucy.\n"
                f"En cuanto verifiquemos disponibilidad te contactamos con los datos para el pago.\n\n"
                f"Sigue el estado de tu pedido aquí:\n{tracking_url}\n\n"
                f"¡Gracias por tu preferencia!"
            )
        try:
            await _enviar_whatsapp(telefono, msg)
        except Exception:
            pass

    return {"ok": True, "folio": numero, "tracking_token": tracking_token, "pedido_id": pedido.id}


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
        # Try to parse structured cambio with product options
        import json
        try:
            cambio_data = json.loads(pedido.nota_florista)
            opciones = cambio_data.get("opciones", [])
            florista_cambio = {
                "tipo": "cambio",
                "nota": cambio_data.get("nota", ""),
                "item_original": cambio_data.get("item_original"),
                "opciones": opciones,
                "requiere_respuesta": True,
            }
        except (json.JSONDecodeError, TypeError):
            # Fallback for plain text nota
            florista_cambio = {
                "tipo": "cambio",
                "nota": pedido.nota_florista,
                "opciones": [],
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

    # Obtener teléfono del cliente para mostrarlo en el banner de validación
    # (anti-error: cliente verifica si el número al que llegan notificaciones es el suyo).
    # Solo se muestra si el pedido NO ha sido pagado todavía: si ya pagó, se da por hecho
    # que recibió correctamente los datos de pago por WhatsApp.
    cliente_tel = None
    if pedido.customer_id and not pedido.pago_confirmado:
        from app.models.clientes import Cliente
        cli_r = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
        cli = cli_r.scalar_one_or_none()
        if cli and cli.telefono:
            # Mostrar número completo formateado para que cliente pueda validar dígito por dígito.
            # Ej: '+52 614 207 0297' (sin enmascarar — el cliente ya está autenticado por el token).
            tel_digits = ''.join(c for c in cli.telefono if c.isdigit())
            tel_10 = tel_digits[-10:] if len(tel_digits) >= 10 else tel_digits
            if len(tel_10) == 10:
                cliente_tel = f"+52 {tel_10[0:3]} {tel_10[3:6]} {tel_10[6:10]}"
            else:
                cliente_tel = f"+52 {tel_digits}"

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
        "cliente_tel_masked": cliente_tel,
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

    producto_elegido_id = data.get("producto_elegido_id")

    if acepta:
        pedido.estado_florista = "pendiente_aprobacion"
        if producto_elegido_id:
            # Look up the new product
            prod_result = await db.execute(select(Producto).where(Producto.id == producto_elegido_id))
            prod = prod_result.scalar_one_or_none()
            prod_name = prod.nombre if prod else f"ID:{producto_elegido_id}"
            nota_respuesta = f"[CLIENTE ELIGE: {prod_name}] {mensaje}".strip()

            # Replace the original item in the order
            if prod and pedido.nota_florista:
                import json
                try:
                    cambio_data = json.loads(pedido.nota_florista)
                    item_original_name = cambio_data.get("item_original")
                    if item_original_name:
                        # Find the ItemPedido matching the original product name
                        items_result = await db.execute(
                            select(ItemPedido).where(ItemPedido.pedido_id == pedido.id)
                        )
                        for item in items_result.scalars().all():
                            old_prod = await db.execute(select(Producto).where(Producto.id == item.producto_id))
                            old_prod = old_prod.scalar_one_or_none()
                            if old_prod and old_prod.nombre == item_original_name:
                                # Replace with new product
                                old_price = item.precio_unitario * item.cantidad
                                item.producto_id = prod.id
                                new_price_unit = prod.precio_descuento if (prod.precio_descuento and prod.precio_descuento < prod.precio) else prod.precio
                                item.precio_unitario = new_price_unit
                                # Recalculate totals
                                new_price = new_price_unit * item.cantidad
                                pedido.subtotal = pedido.subtotal - old_price + new_price
                                pedido.total = pedido.total - old_price + new_price
                                break
                except (json.JSONDecodeError, TypeError):
                    pass
        else:
            nota_respuesta = f"[CLIENTE ACEPTA CAMBIO] {mensaje}" if mensaje else "[CLIENTE ACEPTA CAMBIO]"
    else:
        era_modificacion = pedido.estado_florista == "aprobado_con_modificacion"
        if era_modificacion:
            # Cliente rechaza modificación → cancelar pedido
            pedido.estado = EP.CANCELADO
            pedido.estado_florista = EF.RECHAZADO
            pedido.cancelado_razon = "Cliente rechazó la modificación del florista"
            nota_respuesta = f"[CLIENTE RECHAZA MODIFICACION — CANCELADO] {mensaje}" if mensaje else "[CLIENTE RECHAZA MODIFICACION — CANCELADO]"
        else:
            # Cliente rechaza cambio de producto → requiere atención humana
            pedido.estado_florista = "requiere_atencion"
            pedido.requiere_humano = True
            nota_respuesta = f"[CLIENTE RECHAZA CAMBIO] {mensaje}" if mensaje else "[CLIENTE RECHAZA CAMBIO]"

    # Append to notas_internas
    if pedido.notas_internas:
        pedido.notas_internas += f" | {nota_respuesta}"
    else:
        pedido.notas_internas = nota_respuesta

    await db.commit()

    # Si se canceló por rechazo de modificación, notificar por WhatsApp
    if not acepta and pedido.estado == EP.CANCELADO and pedido.customer_id:
        try:
            from app.models.clientes import Cliente
            cli_r = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cliente = cli_r.scalar_one_or_none()
            if cliente and cliente.telefono:
                msg = (
                    f"Hola {cliente.nombre.split()[0]} 🌸\n\n"
                    f"Tu pedido {pedido.numero} ha sido cancelado porque la modificación propuesta no fue aceptada.\n\n"
                    f"Si deseas, puedes hacer un nuevo pedido:\nhttps://www.florerialucy.com/catalogo/"
                )
                await _enviar_whatsapp(cliente.telefono, msg)
        except Exception:
            pass

    return {"ok": True, "nuevo_estado": pedido.estado_florista, "estado": pedido.estado}
