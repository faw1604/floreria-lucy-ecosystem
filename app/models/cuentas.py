from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CuentaTransferencia(Base):
    __tablename__ = "cuentas_transferencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    banco: Mapped[str] = mapped_column(String(100))
    titular: Mapped[str] = mapped_column(String(200))
    tarjeta: Mapped[str] = mapped_column(String(30))
    clabe: Mapped[str] = mapped_column(String(30))
    activa: Mapped[bool] = mapped_column(Boolean, default=False)
