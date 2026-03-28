from sqlalchemy import String, Integer, Text, DateTime, Date
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from datetime import datetime, date
from app.database import Base
from app.core.config import TZ


class Egreso(Base):
    __tablename__ = "egresos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date)
    concepto: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(50))  # insumos|nómina|servicios|mantenimiento|otro
    monto: Mapped[int] = mapped_column(Integer)  # en centavos
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(TZ))
