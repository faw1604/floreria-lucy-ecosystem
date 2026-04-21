from fastapi import APIRouter, Depends, HTTPException, Cookie, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import os
import cloudinary
import cloudinary.uploader
from app.database import get_db
from app.models.pedidos import Pedido, ItemPedido
from app.models.productos import Producto
from app.models.clientes import Cliente
from app.core.config import TZ
from app.core.utils import ahora
from app.core.estados import EstadoPedido as EP
from app.models.configuracion import ConfiguracionNegocio
from app.routers.auth import verificar_sesion, _parse_token

router = APIRouter()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "ddku2wmpk"),
    api_key=os.getenv("CLOUDINARY_API_KEY", ""),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
)

from app.core.zonas import ZONA_ORDER, orden_zona

HORARIO_ORDER = {"mañana": 0, "manana": 0, "tarde": 1, "noche": 2}


def _sort_key(p):
    h = HORARIO_ORDER.get((p.horario_entrega or "").lower(), 9)
    z = orden_zona(p.zona_entrega)
    return (h, z)


async def _pedido_items_nombres(pedido_id: int, db: AsyncSession) -> list[str]:
    """Obtener nombres de items en 1 query con JOIN (no N+1)."""
    from sqlalchemy import outerjoin
    result = await db.execute(
        select(ItemPedido, Producto.nombre)
        .outerjoin(Producto, ItemPedido.producto_id == Producto.id)
        .where(ItemPedido.pedido_id == pedido_id)
    )
    nombres = []
    for item, prod_nombre in result.all():
        if item.es_personalizado and item.nombre_personalizado:
            nombres.append(item.nombre_personalizado)
        elif prod_nombre:
            nombres.append(prod_nombre)
    return nombres


@router.get("/config-temporada")
async def config_temporada(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Devuelve si la temporada alta está activa."""
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(ConfiguracionNegocio).where(ConfiguracionNegocio.clave == "claudia_temporada_alta")
    )
    cfg = result.scalar_one_or_none()
    return {"temporada_alta": cfg.valor == "true" if cfg else False}


@router.get("/entregas-hoy")
async def entregas_hoy(
    fecha: str = "hoy",
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    # Obtener ID del repartidor logueado
    info = _parse_token(panel_session)
    mi_id = info["id"] if info else None

    from datetime import timedelta, date as date_type
    fecha_hoy = datetime.now(TZ).date()
    manana = fecha_hoy + timedelta(days=1)
    ayer = fecha_hoy - timedelta(days=1)
    estados = EP.LISTOS + [EP.EN_CAMINO, EP.ENTREGADO, EP.INTENTO_FALLIDO]
    if fecha == "manana":
        fecha_target = manana
    elif fecha == "ayer":
        fecha_target = ayer
    elif fecha == "todos":
        query = select(Pedido).where(Pedido.fecha_entrega.in_([fecha_hoy, manana]), Pedido.estado.in_(estados))
        fecha_target = None
    elif fecha != "hoy":
        # Fecha específica: YYYY-MM-DD
        try:
            fecha_target = date_type.fromisoformat(fecha)
        except ValueError:
            fecha_target = fecha_hoy
    else:
        fecha_target = fecha_hoy

    if fecha != "todos":
        query = select(Pedido).where(Pedido.fecha_entrega == fecha_target, Pedido.estado.in_(estados))

    # Filtrar solo envíos
    from sqlalchemy import or_
    query = query.where(Pedido.metodo_entrega.in_(["envio", "funeral_envio"]))
    # Admin ve todos, repartidor solo los suyos + sin asignar
    mi_rol = info.get("r") if info else None
    if mi_rol != "admin":
        query = query.where(
            or_(Pedido.repartidor_id == mi_id, Pedido.repartidor_id.is_(None))
        )

    result = await db.execute(query)
    pedidos = sorted(result.scalars().all(), key=_sort_key)

    # Pre-fetch all clientes in 1 query (avoid N+1)
    customer_ids = [p.customer_id for p in pedidos if p.customer_id]
    clientes_map = {}
    if customer_ids:
        cli_result = await db.execute(select(Cliente).where(Cliente.id.in_(customer_ids)))
        for cli in cli_result.scalars().all():
            clientes_map[cli.id] = cli

    # Pre-fetch funerarias para pedidos funeral (mapear por nombre)
    from app.models.funerarias import Funeraria
    import re
    fun_nombres = set()
    for p in pedidos:
        if p.tipo_especial == "Funeral" and p.notas_internas:
            m = re.search(r"Funeraria:\s*([^|]+)", p.notas_internas, re.IGNORECASE)
            if m:
                fun_nombres.add(m.group(1).strip())
    funerarias_map = {}
    if fun_nombres:
        fun_result = await db.execute(select(Funeraria).where(Funeraria.nombre.in_(fun_nombres)))
        for f in fun_result.scalars().all():
            funerarias_map[f.nombre] = f

    out = []
    for p in pedidos:
        items = await _pedido_items_nombres(p.id, db)
        cli = clientes_map.get(p.customer_id)
        cliente_nombre = cli.nombre if cli else None
        cliente_telefono = cli.telefono if cli else None
        # Para pedidos funeral: usar dirección de la funeraria si no hay direccion_entrega
        direccion = p.direccion_entrega
        if not direccion and p.tipo_especial == "Funeral" and p.notas_internas:
            m = re.search(r"Funeraria:\s*([^|]+)", p.notas_internas, re.IGNORECASE)
            if m:
                fun_nombre = m.group(1).strip()
                fun = funerarias_map.get(fun_nombre)
                if fun and fun.direccion:
                    direccion = f"{fun.nombre} — {fun.direccion}"
                elif fun_nombre:
                    direccion = fun_nombre
        out.append({
            "id": p.id,
            "folio": p.numero,
            "horario_entrega": p.horario_entrega,
            "zona_envio": p.zona_entrega,
            "nombre_destinatario": p.receptor_nombre,
            "telefono_destinatario": p.receptor_telefono,
            "direccion_entrega": direccion,
            "dedicatoria": p.dedicatoria,
            "notas_entrega": p.notas_internas,
            "metodo_pago": p.forma_pago,
            "total": p.total,
            "items": items,
            "estado": p.estado,
            "foto_entrega_url": p.foto_entrega_url,
            "nota_no_entrega": p.nota_no_entrega,
            "cliente_nombre": cliente_nombre,
            "cliente_telefono": cliente_telefono,
            "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None,
            "ruta": p.ruta,
            "tipo_especial": p.tipo_especial,
            "metodo_entrega": p.metodo_entrega,
            "inicio_ruta_at": p.inicio_ruta_at.isoformat() if p.inicio_ruta_at else None,
            "entregado_at": p.entregado_at.isoformat() if p.entregado_at else None,
            "repartidor_id": p.repartidor_id,
        })
    return out


@router.post("/iniciar-ruta")
async def iniciar_ruta(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    info = _parse_token(panel_session)
    mi_id = info["id"] if info else None
    data = await request.json()
    ids = data.get("pedido_ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="No se enviaron pedidos")
    ts = ahora()
    count = 0
    for pid in ids:
        result = await db.execute(select(Pedido).where(Pedido.id == pid))
        pedido = result.scalar_one_or_none()
        if pedido and pedido.estado in EP.LISTOS:
            pedido.estado = EP.EN_CAMINO
            pedido.inicio_ruta_at = ts
            pedido.repartidor_id = mi_id
            count += 1
    await db.commit()
    return {"ok": True, "actualizados": count}


@router.post("/entregar/{pedido_id}")
async def entregar(
    pedido_id: int,
    foto: UploadFile = File(...),
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    if not foto or not foto.filename:
        raise HTTPException(status_code=400, detail="La foto es obligatoria")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    ts_now = ahora()
    ts_int = int(ts_now.timestamp())
    folio = (pedido.numero or "").replace("-", "_")
    contenido = await foto.read()

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        upload_result = await loop.run_in_executor(
            None,
            lambda: cloudinary.uploader.upload(
                contenido,
                folder="entregas/",
                public_id=f"{folio}_{ts_int}",
                resource_type="image",
            )
        )
        foto_url = upload_result.get("secure_url", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir foto: {str(e)}")

    pedido.estado = EP.ENTREGADO
    pedido.entregado_at = ts_now
    pedido.foto_entrega_url = foto_url
    # Guardar datos para WhatsApp antes del commit
    _wa_tel = None
    _wa_nombre = None
    _wa_folio = pedido.numero
    if pedido.customer_id:
        from app.models.clientes import Cliente
        cli_r = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
        cli = cli_r.scalar_one_or_none()
        if cli and cli.telefono:
            _wa_tel = cli.telefono
            _wa_nombre = cli.nombre.split()[0] if cli.nombre else ""
    await db.commit()

    # WhatsApp al cliente en background — no bloquear al repartidor
    if _wa_tel:
        import asyncio
        async def _send_wa():
            try:
                from app.routers.catalogo import _enviar_whatsapp
                await _enviar_whatsapp(_wa_tel,
                    f"Hola {_wa_nombre} 🌸\n\n"
                    f"Tu pedido {_wa_folio} fue entregado!\n\n"
                    f"Gracias por tu preferencia. Esperamos verte pronto!\n"
                    f"— Floreria Lucy"
                )
            except Exception:
                pass
        asyncio.create_task(_send_wa())

    return {"ok": True, "foto_url": foto_url}


@router.post("/no-entrega/{pedido_id}")
async def no_entrega(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    motivo = data.get("motivo", "")
    if not motivo:
        raise HTTPException(status_code=400, detail="El motivo es obligatorio")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    ts_now = ahora()
    pedido.estado = EP.INTENTO_FALLIDO
    pedido.intento_fallido_at = ts_now
    pedido.nota_no_entrega = motivo
    await db.commit()
    return {"ok": True}


@router.post("/asignar/{pedido_id}")
async def asignar_repartidor(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Admin asigna repartidor a un pedido."""
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    repartidor_id = data.get("repartidor_id")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    pedido.repartidor_id = repartidor_id
    await db.commit()
    return {"ok": True}


@router.post("/optimizar-ruta")
async def optimizar_ruta(
    request: Request,
    panel_session: str | None = Cookie(default=None),
):
    """Optimiza el orden de visitas usando Google Routes API.
    Recibe lista de pedidos {id, direccion} y devuelve el orden óptimo.
    Origen: Florería Lucy (C. Sabino 610, Las Granjas, Chihuahua)."""
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    pedidos = data.get("pedidos", [])
    if not pedidos or len(pedidos) < 2:
        # Con 1 entrega o menos no hay nada que optimizar
        return {"orden": [p.get("id") for p in pedidos]}

    google_key = os.getenv("GOOGLE_GEOCODING_KEY", "")
    if not google_key:
        # Sin API key, devolver orden original
        return {"orden": [p.get("id") for p in pedidos], "warning": "Sin API key"}

    import httpx
    origen = "C. Sabino 610, Las Granjas, Chihuahua, México"
    # Google Routes API: usa intermediates para waypoints, optimizeWaypointOrder=true
    payload = {
        "origin": {"address": origen},
        "destination": {"address": pedidos[-1].get("direccion", "") + ", Chihuahua, México"},
        "intermediates": [{"address": p.get("direccion", "") + ", Chihuahua, México"} for p in pedidos[:-1]],
        "travelMode": "DRIVE",
        "optimizeWaypointOrder": True,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": google_key,
        "X-Goog-FieldMask": "routes.optimizedIntermediateWaypointIndex",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                json=payload, headers=headers,
            )
            if r.status_code != 200:
                return {"orden": [p.get("id") for p in pedidos], "warning": f"Routes API: {r.status_code}"}
            result = r.json()
            routes = result.get("routes", [])
            if not routes:
                return {"orden": [p.get("id") for p in pedidos], "warning": "Sin rutas"}
            # optimizedIntermediateWaypointIndex devuelve el orden óptimo de intermediates
            # Ej: [2, 0, 1] significa: del array intermediates, ir 2 → 0 → 1, luego destination
            opt_order = routes[0].get("optimizedIntermediateWaypointIndex", [])
            if not opt_order:
                return {"orden": [p.get("id") for p in pedidos]}
            # Reconstruir orden: intermedios reordenados + último (destination)
            orden_ids = [pedidos[i].get("id") for i in opt_order] + [pedidos[-1].get("id")]
            return {"orden": orden_ids, "optimizado": True}
    except Exception as e:
        return {"orden": [p.get("id") for p in pedidos], "warning": str(e)}
