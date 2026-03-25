from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class TipoFlor(Base):
    __tablename__ = "tipos_flor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    costo_unitario: Mapped[int] = mapped_column(Integer, default=0)  # en centavos
    disponible_hoy: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductoFlor(Base):
    __tablename__ = "producto_flores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    producto_id: Mapped[int] = mapped_column(Integer, index=True)
    flor_id: Mapped[int] = mapped_column(Integer, index=True)
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
