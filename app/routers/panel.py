from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import os
from app.database import get_db
from app.core.config import TZ
from app.routers.auth import verificar_sesion

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
async def estado_horario(panel_session: str | None = Cookie(default=None)):
    ahora = datetime.now(TZ)
    dia = ahora.weekday()
    nombres_dia = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    en_horario = esta_en_horario(ahora)
    return {
        "abierto": en_horario,
        "dia": nombres_dia[dia],
        "hora_chihuahua": ahora.strftime("%H:%M"),
        "horario_hoy": HORARIO_FLORERIA.get(dia, (0, 0)),
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

@router.get("/envio/tarifa")
async def tarifa_envio(zona: str | None = None):
    tarifas = {
        "Morada": 9900,
        "Azul": 15900,
        "Verde": 19900,
    }
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
    from sqlalchemy import select, func
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

@router.get("/", response_class=HTMLResponse)
async def panel_html(panel_session: str | None = Cookie(default=None)):
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
    from sqlalchemy import select, func
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
