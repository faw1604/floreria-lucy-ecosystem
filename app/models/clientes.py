from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100))
    telefono: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    direccion_default: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fuente: Mapped[str] = mapped_column(String(20), default="WhatsApp")  # WhatsApp / Mostrador / Web
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
