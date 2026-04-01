"""
Utilidades centralizadas del sistema Florería Lucy.
"""
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import TZ


def ahora() -> datetime:
    """Datetime actual en Chihuahua, naive (sin timezone) para asyncpg.

    asyncpg no acepta datetime aware en columnas TIMESTAMP sin timezone.
    Esta función devuelve la hora de Chihuahua como naive datetime.
    """
    return datetime.now(TZ).replace(tzinfo=None)


def hoy():
    """Fecha actual en Chihuahua."""
    return datetime.now(TZ).date()


async def generar_folio(db: AsyncSession) -> str:
    """Genera folio único FL-YYYY-XXXX usando MAX del año actual.

    Usado por POS, catálogo web y pedidos de WhatsApp.
    Un solo generador para evitar duplicados y lógica inconsistente.
    """
    from app.models.pedidos import Pedido
    yr = datetime.now(TZ).strftime("%Y")
    prefix = f"FL-{yr}-"
    result = await db.execute(
        select(func.max(Pedido.numero)).where(Pedido.numero.like(f"{prefix}%"))
    )
    max_num = result.scalar()
    if max_num:
        try:
            last = int(max_num.split("-")[-1])
        except (ValueError, IndexError):
            last = 0
    else:
        last = 0
    # Mínimos por año: 2026 empieza en 5000, 2027+ en 1000
    minimo = 4999 if yr == "2026" else 999
    if last < minimo:
        last = minimo
    return f"{prefix}{str(last + 1).zfill(4)}"
