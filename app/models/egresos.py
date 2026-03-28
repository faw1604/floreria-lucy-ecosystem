from sqlalchemy import String, Integer, Text, DateTime, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from datetime import datetime, date
from app.database import Base
from app.core.config import TZ


class CategoriaGasto(Base):
    __tablename__ = "categorias_gasto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class MetodoPagoEgreso(Base):
    __tablename__ = "metodos_pago_egreso"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Egreso(Base):
    __tablename__ = "egresos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date)
    concepto: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(50))
    monto: Mapped[int] = mapped_column(Integer)  # en centavos
    metodo_pago: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proveedor: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referencia: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    es_recurrente: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(TZ))


class OtroIngreso(Base):
    __tablename__ = "otros_ingresos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date)
    concepto: Mapped[str] = mapped_column(String(200))
    monto: Mapped[int] = mapped_column(Integer)  # centavos
    metodo_pago: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(TZ))


class GastoRecurrente(Base):
    __tablename__ = "gastos_recurrentes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(50))
    frecuencia: Mapped[str] = mapped_column(String(20))  # mensual|quincenal|semanal
    monto_sugerido: Mapped[int] = mapped_column(Integer)  # centavos
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
