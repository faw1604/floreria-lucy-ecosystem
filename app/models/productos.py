from sqlalchemy import String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    nombre: Mapped[str] = mapped_column(String(200), index=True)
    categoria: Mapped[str] = mapped_column(String(100))
    precio: Mapped[int] = mapped_column(Integer)  # en centavos
    costo: Mapped[int] = mapped_column(Integer, default=0)  # en centavos
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    disponible_hoy: Mapped[bool] = mapped_column(Boolean, default=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_descuento: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etiquetas: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array: ["rosas","romántico"]
    dimensiones: Mapped[str | None] = mapped_column(Text, nullable=True)  # ej: "30cm x 40cm"
