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
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    import httpx
    data = await request.json()
    mensaje = data.get("mensaje", "")
    historial = data.get("historial", [])

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    if not ANTHROPIC_API_KEY:
        return {"respuesta": "No hay API key de Anthropic configurada. Agrégala en las variables de Railway."}

    system = """Eres el asistente de administración de Florería Lucy en Chihuahua, México.
Tienes acceso al ecosistema del negocio: pedidos, inventario, flores, productos, finanzas y configuración.
Responde en español, de forma directa y útil. Eres conciso — el dueño está ocupado.
Cuando te pregunten por pendientes del día, menciona: pedidos sin confirmar pago, flores que podrían escasear, pagos recurrentes próximos."""

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
