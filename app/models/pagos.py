from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class MetodoPago(Base):
    __tablename__ = "metodos_pago"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(30))  # transferencia / oxxo / link_tarjeta / tarjeta_fisica
    banco: Mapped[str | None] = mapped_column(String(50), nullable=True)
    titular: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clabe: Mapped[str | None] = mapped_column(String(20), nullable=True)
    numero_tarjeta: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    solo_sucursal: Mapped[bool] = mapped_column(Boolean, default=False)
