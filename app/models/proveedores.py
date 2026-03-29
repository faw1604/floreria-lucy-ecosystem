from sqlalchemy import String, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(200))
    contacto: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
