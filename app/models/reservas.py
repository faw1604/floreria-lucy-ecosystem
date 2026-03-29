from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.database import Base


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    producto_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    nombre_custom: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    precio: Mapped[int] = mapped_column(Integer)  # centavos
    foto_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    florista_usuario: Mapped[str] = mapped_column(String(100))
    estado: Mapped[str] = mapped_column(String(20), default="disponible")
    # disponible / vendida / descartada
    pedido_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    vendida_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    descartada_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    descarte_razon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
