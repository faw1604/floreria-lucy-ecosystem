from sqlalchemy import String, Integer, Boolean, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from datetime import datetime, date
from app.database import Base
from app.core.config import TZ


class CuentaTransferencia(Base):
    __tablename__ = "cuentas_transferencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    banco: Mapped[str] = mapped_column(String(100))
    titular: Mapped[str] = mapped_column(String(200))
    tarjeta: Mapped[str] = mapped_column(String(30))
    clabe: Mapped[str] = mapped_column(String(30))
    activa: Mapped[bool] = mapped_column(Boolean, default=False)


class CuentaFinanciera(Base):
    """Cuenta de balance: Caja (efectivo POS) y Caja Chica (fondo pagos)."""
    __tablename__ = "cuentas_financieras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))  # caja | caja_chica
    saldo_inicial: Mapped[int] = mapped_column(Integer, default=0)  # centavos
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fondo_base: Mapped[int] = mapped_column(Integer, default=0)  # solo Caja = $1000
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(TZ).replace(tzinfo=None)
    )


class MovimientoCuenta(Base):
    """Movimientos contables sobre CuentaFinanciera (depósitos, retiros, transferencias).
    Los egresos NO se duplican aquí; se calculan aparte."""
    __tablename__ = "movimientos_cuenta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cuenta_id: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[date] = mapped_column(Date)
    tipo: Mapped[str] = mapped_column(String(30))
    # tipos: deposito_corte_pos | retiro_manual | deposito_manual |
    #        transferencia_in | transferencia_out | ajuste
    concepto: Mapped[str] = mapped_column(String(200))
    monto: Mapped[int] = mapped_column(Integer)  # centavos, siempre positivo
    cuenta_destino_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    referencia_tipo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    referencia_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(TZ).replace(tzinfo=None)
    )
