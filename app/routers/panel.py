from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from datetime import datetime
import os
from app.database import get_db
from app.core.config import TZ
from app.routers.auth import verificar_sesion
from app.models.pedidos import Pedido
from app.models.clientes import Cliente
from app.models.configuracion import HorarioEspecifico

router = APIRouter()

HORARIO_FLORERIA = {
    0: (9, 19),
    1: (9, 19),
    2: (9, 19),
    3: (9, 19),
    4: (9, 19),
    5: (10, 18),
    6: (11, 15),
}

def esta_en_horario(ahora: datetime) -> bool:
    dia = ahora.weekday()
    hora_actual = ahora.hour + ahora.minute / 60
    if dia not in HORARIO_FLORERIA:
        return False
    hora_apertura, hora_cierre = HORARIO_FLORERIA[dia]
    return hora_apertura <= hora_actual < hora_cierre

@router.get("/horario/estado")
async def estado_horario(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    ahora_dt = datetime.now(TZ)
    dia = ahora_dt.weekday()
    nombres_dia = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    en_horario = esta_en_horario(ahora_dt)

    # Read temporada from configuracion_negocio
    from app.models.configuracion import ConfiguracionNegocio
    result = await db.execute(select(ConfiguracionNegocio))
    cfg = {c.clave: c.valor for c in result.scalars().all()}
    temporada_activa = cfg.get("temporada_modo") == "alta"
    temporada_categoria = cfg.get("temporada_categoria", "")

    return {
        "abierto": en_horario,
        "dia": nombres_dia[dia],
        "hora_chihuahua": ahora_dt.strftime("%H:%M"),
        "horario_hoy": HORARIO_FLORERIA.get(dia, (0, 0)),
        "temporada_activa": temporada_activa and bool(temporada_categoria),
        "temporada_nombre": temporada_categoria if temporada_activa else None,
        "temporada_categoria": temporada_categoria if temporada_activa else None,
    }

@router.get("/horario/entregas")
async def horarios_entregas(fecha: str | None = None):
    ahora = datetime.now(TZ)
    hora_actual = ahora.hour + ahora.minute / 60

    horarios = []
    if hora_actual < 11:
        horarios.append({"id": "manana", "label": "Entre 9am y 2pm", "cierre": "11:00am"})
    if hora_actual < 16:
        horarios.append({"id": "tarde", "label": "Entre 2pm y 6pm", "cierre": "4:00pm"})
    if hora_actual < 18.83:
        horarios.append({"id": "noche", "label": "Entre 6pm y 9pm", "cierre": "6:50pm"})

    return {"horarios_disponibles": horarios, "hora_actual": ahora.strftime("%H:%M")}

@router.get("/alertas-fechas")
async def alertas_fechas(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    from app.models.clientes import Cliente

    ahora = datetime.now(TZ)
    hoy = ahora.date()
    cumpleanos = []
    aniversarios = []

    result = await db.execute(
        select(Cliente).where(
            Cliente.fecha_nacimiento.isnot(None)
        )
    )
    for c in result.scalars().all():
        fn = c.fecha_nacimiento
        try:
            este_ano = fn.replace(year=hoy.year)
        except ValueError:
            continue
        diff = (este_ano - hoy).days
        if 0 <= diff <= 3:
            cumpleanos.append({"nombre": c.nombre, "telefono": c.telefono, "dias_faltan": diff, "fecha": str(este_ano)})

    # Check fecha_aniversario (legacy)
    result2 = await db.execute(
        select(Cliente).where(
            Cliente.fecha_aniversario.isnot(None)
        )
    )
    for c in result2.scalars().all():
        fa = c.fecha_aniversario
        try:
            este_ano = fa.replace(year=hoy.year)
        except ValueError:
            continue
        diff = (este_ano - hoy).days
        if 0 <= diff <= 3:
            aniversarios.append({"nombre": c.nombre, "telefono": c.telefono, "dias_faltan": diff, "fecha": str(este_ano), "tipo": "Aniversario"})

    # Check fechas_especiales (new JSON field)
    import json as _json
    result3 = await db.execute(
        select(Cliente).where(
            Cliente.fechas_especiales.isnot(None)
        )
    )
    for c in result3.scalars().all():
        try:
            fechas = _json.loads(c.fechas_especiales)
        except Exception:
            continue
        for fe in fechas:
            try:
                fd = date.fromisoformat(fe["fecha"])
                este_ano = fd.replace(year=hoy.year)
            except (ValueError, KeyError):
                continue
            diff = (este_ano - hoy).days
            if 0 <= diff <= 3:
                aniversarios.append({"nombre": c.nombre, "telefono": c.telefono, "dias_faltan": diff, "fecha": str(este_ano), "tipo": fe.get("nombre", "Fecha especial")})

    return {"cumpleanos_proximos": cumpleanos, "aniversarios_proximos": aniversarios}

@router.get("/envio/tarifa")
async def tarifa_envio(zona: str | None = None):
    from app.services.zonas_envio import _ZONAS
    tarifas = {nombre: tarifa * 100 for nombre, tarifa, _ in _ZONAS}
    if zona and zona in tarifas:
        return {"zona": zona, "tarifa": tarifas[zona], "tarifa_display": f"${tarifas[zona] // 100}"}
    return {"zonas": [{"zona": z, "tarifa": t, "tarifa_display": f"${t // 100}"} for z, t in tarifas.items()]}

@router.get("/stats")
async def stats_del_dia(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")

    from app.models.pedidos import Pedido
    hoy = datetime.now(TZ).date()
    result = await db.execute(
        select(
            func.count(Pedido.id).label("total_pedidos"),
            func.sum(Pedido.total).label("total_ventas"),
        ).where(Pedido.fecha_entrega == hoy)
    )
    row = result.one()
    return {
        "fecha": str(hoy),
        "total_pedidos": row.total_pedidos or 0,
        "total_ventas": row.total_ventas or 0,
        "total_ventas_display": f"${(row.total_ventas or 0) // 100:,}",
    }

@router.get("/stats/semana")
async def stats_semana(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")

    from datetime import timedelta
    from app.models.pedidos import Pedido, ItemPedido
    from app.models.productos import Producto

    hoy = datetime.now(TZ).date()
    inicio_semana = hoy - timedelta(days=6)

    # Ventas por día (últimos 7 días)
    result = await db.execute(
        select(
            Pedido.fecha_entrega,
            func.count(Pedido.id).label("pedidos"),
            func.sum(Pedido.total).label("ventas"),
        )
        .where(Pedido.fecha_entrega >= inicio_semana, Pedido.fecha_entrega <= hoy)
        .group_by(Pedido.fecha_entrega)
        .order_by(Pedido.fecha_entrega)
    )
    rows = result.all()
    ventas_por_dia = []
    for r in rows:
        ventas_por_dia.append({
            "fecha": str(r.fecha_entrega),
            "pedidos": r.pedidos or 0,
            "ventas": r.ventas or 0,
            "ventas_display": f"${(r.ventas or 0) // 100:,}",
        })

    # Ticket promedio de la semana
    result2 = await db.execute(
        select(func.avg(Pedido.total))
        .where(Pedido.fecha_entrega >= inicio_semana, Pedido.fecha_entrega <= hoy, Pedido.total > 0)
    )
    ticket_promedio = result2.scalar() or 0

    # Producto más vendido (por cantidad)
    result3 = await db.execute(
        select(Producto.nombre, func.sum(ItemPedido.cantidad).label("total_qty"))
        .join(Producto, Producto.id == ItemPedido.producto_id)
        .join(Pedido, Pedido.id == ItemPedido.pedido_id)
        .where(Pedido.fecha_entrega >= inicio_semana, Pedido.fecha_entrega <= hoy)
        .group_by(Producto.nombre)
        .order_by(func.sum(ItemPedido.cantidad).desc())
        .limit(1)
    )
    top_producto_row = result3.first()
    top_producto = {
        "nombre": top_producto_row[0] if top_producto_row else "Sin datos",
        "cantidad": top_producto_row[1] if top_producto_row else 0,
    }

    # Canal más usado
    result4 = await db.execute(
        select(Pedido.canal, func.count(Pedido.id).label("total"))
        .where(Pedido.fecha_entrega >= inicio_semana, Pedido.fecha_entrega <= hoy)
        .group_by(Pedido.canal)
        .order_by(func.count(Pedido.id).desc())
        .limit(1)
    )
    top_canal_row = result4.first()
    top_canal = {
        "canal": top_canal_row[0] if top_canal_row else "Sin datos",
        "pedidos": top_canal_row[1] if top_canal_row else 0,
    }

    return {
        "periodo": {"inicio": str(inicio_semana), "fin": str(hoy)},
        "ventas_por_dia": ventas_por_dia,
        "ticket_promedio": int(ticket_promedio),
        "ticket_promedio_display": f"${int(ticket_promedio) // 100:,}",
        "producto_mas_vendido": top_producto,
        "canal_mas_usado": top_canal,
    }

def _check_role(panel_session, allowed_roles):
    from app.routers.auth import obtener_rol
    rol = obtener_rol(panel_session)
    if not rol:
        return HTMLResponse('<script>location.href="/panel/"</script>')
    if rol not in allowed_roles:
        return HTMLResponse('<script>location.href="/panel/"</script>')
    return None

@router.get("/pos", response_class=HTMLResponse)
async def pos_html(panel_session: str | None = Cookie(default=None)):
    block = _check_role(panel_session, ["admin", "operador"])
    if block: return block
    try:
        with open("app/pos.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="pos.html no encontrado")

@router.get("/repartidor", response_class=HTMLResponse)
async def repartidor_html(panel_session: str | None = Cookie(default=None)):
    block = _check_role(panel_session, ["admin", "repartidor"])
    if block: return block
    try:
        with open("app/repartidor.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="repartidor.html no encontrado")

@router.get("/taller", response_class=HTMLResponse)
async def taller_html(panel_session: str | None = Cookie(default=None)):
    block = _check_role(panel_session, ["admin", "florista"])
    if block: return block
    try:
        with open("app/taller.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="taller.html no encontrado")

@router.get("/reset-session")
async def reset_session():
    """Borra cookies y redirige al login."""
    response = HTMLResponse('<html><body><script>document.cookie="panel_session=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT";location.href="/panel/";</script></body></html>')
    response.delete_cookie("panel_session", path="/")
    response.delete_cookie("panel_session", path="/auth")
    response.delete_cookie("panel_session", path="/panel")
    response.delete_cookie("panel_session")
    return response


@router.get("/", response_class=HTMLResponse)
async def panel_html(panel_session: str | None = Cookie(default=None)):
    from app.routers.auth import obtener_rol
    rol = obtener_rol(panel_session)
    # Not authenticated — show login page
    if not rol:
        try:
            with open("app/login.html", "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        except FileNotFoundError:
            return HTMLResponse('<h1>Login not found</h1>', status_code=500)
    # Redirect non-admin to their panel
    redirects = {"operador": "/panel/pos", "florista": "/panel/taller", "repartidor": "/panel/repartidor"}
    if rol in redirects:
        return HTMLResponse(f'<script>location.href="{redirects[rol]}"</script>')
    # Admin — show admin panel
    try:
        with open("app/admin.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="admin.html no encontrado")

@router.get("/legacy", response_class=HTMLResponse)
async def panel_legacy(panel_session: str | None = Cookie(default=None)):
    try:
        with open("app/panel.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="panel.html no encontrado")

@router.post("/asistente")
async def asistente_ia(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    import os
    import httpx

    from app.models.pedidos import Pedido
    from app.models.flores import TipoFlor
    from app.models.pagos import MetodoPago

    data = await request.json()
    mensaje = data.get("mensaje", "")
    historial = data.get("historial", [])

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    if not ANTHROPIC_API_KEY:
        return {"respuesta": "No hay API key de Anthropic configurada."}

    # Obtener datos reales del día
    hoy = datetime.now(TZ).date()

    # Pedidos del día
    result = await db.execute(
        select(Pedido).where(Pedido.fecha_entrega == hoy).order_by(Pedido.horario_entrega)
    )
    pedidos_hoy = result.scalars().all()

    # Pedidos pendientes de pago
    result2 = await db.execute(
        select(Pedido).where(Pedido.pago_confirmado == False, Pedido.estado != 'Cancelado')
    )
    pendientes_pago = result2.scalars().all()

    # Flores no disponibles
    result3 = await db.execute(
        select(TipoFlor).where(TipoFlor.disponible_hoy == False)
    )
    flores_faltantes = result3.scalars().all()

    # Cuenta activa de transferencia
    result4 = await db.execute(
        select(MetodoPago).where(MetodoPago.tipo == "transferencia", MetodoPago.activo == True).limit(1)
    )
    cuenta_activa = result4.scalar_one_or_none()

    # Estadísticas del día
    result5 = await db.execute(
        select(func.count(Pedido.id), func.sum(Pedido.total)).where(Pedido.fecha_entrega == hoy)
    )
    stats = result5.one()

    # Construir contexto real
    contexto_pedidos = ""
    if pedidos_hoy:
        contexto_pedidos = "\n".join([
            f"- #{p.numero} | {p.estado} | {p.receptor_nombre or 'Sin receptor'} | {p.horario_entrega or 'Sin horario'} | ${(p.total or 0)//100} | Pago: {'Confirmado' if p.pago_confirmado else 'PENDIENTE'} | {p.tipo_especial or 'Normal'}"
            for p in pedidos_hoy
        ])
    else:
        contexto_pedidos = "No hay pedidos para hoy."

    contexto_pendientes = ""
    if pendientes_pago:
        contexto_pendientes = "\n".join([
            f"- #{p.numero} | {p.receptor_nombre or 'Sin nombre'} | ${(p.total or 0)//100} | Estado: {p.estado}"
            for p in pendientes_pago
        ])
    else:
        contexto_pendientes = "No hay pedidos pendientes de pago."

    contexto_flores = ""
    if flores_faltantes:
        contexto_flores = ", ".join([f.nombre for f in flores_faltantes])
    else:
        contexto_flores = "Todas las flores están disponibles."

    system = f"""Eres el asistente de administración de Florería Lucy en Chihuahua, México.
Tienes acceso a los datos reales del negocio en este momento.

FECHA Y HORA ACTUAL: {datetime.now(TZ).strftime('%A %d de %B, %H:%M')} (Chihuahua)

ESTADÍSTICAS DEL DÍA:
- Total pedidos hoy: {stats[0] or 0}
- Ventas del día: ${(stats[1] or 0)//100:,}

PEDIDOS DE HOY:
{contexto_pedidos}

PEDIDOS PENDIENTES DE PAGO:
{contexto_pendientes}

FLORES NO DISPONIBLES HOY:
{contexto_flores}

CUENTA BANCARIA ACTIVA PARA TRANSFERENCIAS:
{f"{cuenta_activa.banco} — {cuenta_activa.titular}" if cuenta_activa else "Ninguna activa"}

INSTRUCCIONES:
- Responde en español, directo y conciso. El dueño está ocupado.
- Usa los datos reales de arriba para responder. NUNCA inventes datos.
- Si no tienes el dato que piden, dilo claramente.
- Para pendientes del día menciona: pedidos sin pago confirmado, flores faltantes, cualquier pedido que requiera atención.
- Puedes sugerir acciones concretas basadas en los datos reales."""

    mensajes = []
    for m in historial[-10:]:
        mensajes.append({"role": m["role"], "content": m["content"]})
    mensajes.append({"role": "user", "content": mensaje})

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1024,
                "system": system,
                "messages": mensajes,
            },
            timeout=30,
        )
        d = r.json()
        respuesta = d["content"][0]["text"] if d.get("content") else "Sin respuesta"
        return {"respuesta": respuesta}


@router.get("/pagos-pendientes")
async def pagos_pendientes(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Lista pedidos con comprobante_recibido para verificación de pago."""
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(Pedido)
        .where(Pedido.estado == "comprobante_recibido")
        .order_by(Pedido.comprobante_pago_at.desc())
    )
    pedidos = result.scalars().all()
    items = []
    for p in pedidos:
        nombre_cliente = None
        if p.customer_id:
            cli = await db.execute(select(Cliente).where(Cliente.id == p.customer_id))
            c = cli.scalar_one_or_none()
            if c:
                nombre_cliente = c.nombre
        items.append({
            "id": p.id,
            "numero": p.numero,
            "cliente": nombre_cliente or p.receptor_nombre or "Sin nombre",
            "total": p.total,
            "comprobante_url": p.comprobante_pago_url,
            "comprobante_at": p.comprobante_pago_at.isoformat() if p.comprobante_pago_at else None,
            "canal": p.canal,
        })
    return items


# --- Horarios específicos ---

@router.get("/horarios-especificos")
async def listar_horarios_especificos(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(HorarioEspecifico)
        .where(HorarioEspecifico.activo == True)
        .order_by(HorarioEspecifico.dia_semana, HorarioEspecifico.hora)
    )
    horarios = result.scalars().all()
    return [
        {"id": h.id, "dia_semana": h.dia_semana, "hora": h.hora}
        for h in horarios
    ]


@router.post("/horarios-especificos")
async def agregar_horario_especifico(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    dia = data.get("dia_semana")
    hora = data.get("hora", "").strip()
    if dia is None or not hora:
        raise HTTPException(status_code=400, detail="dia_semana y hora son requeridos")
    h = HorarioEspecifico(dia_semana=dia, hora=hora, activo=True)
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return {"ok": True, "id": h.id, "dia_semana": h.dia_semana, "hora": h.hora}


@router.delete("/horarios-especificos/{horario_id}")
async def eliminar_horario_especifico(
    horario_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(HorarioEspecifico).where(HorarioEspecifico.id == horario_id)
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Horario no encontrado")
    await db.delete(h)
    await db.commit()
    return {"ok": True}
