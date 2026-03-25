from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
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
