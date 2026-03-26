from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InsumoFloral(Base):
    __tablename__ = "insumos_florales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    familia: Mapped[str] = mapped_column(String(100))
    variante: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categoria: Mapped[str] = mapped_column(String(50))  # principal / otras_flores / follajes
    stock_estado: Mapped[str] = mapped_column(String(20), default="en_stock")
    cantidad: Mapped[int] = mapped_column(Integer, default=0)
    descuento_automatico: Mapped[bool] = mapped_column(Boolean, default=False)


class InsumoNoFloral(Base):
    __tablename__ = "insumos_no_florales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoria: Mapped[str] = mapped_column(String(100))
    variante: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stock_estado: Mapped[str] = mapped_column(String(20), default="en_stock")
    cantidad: Mapped[int] = mapped_column(Integer, default=0)


class InsumoProducto(Base):
    __tablename__ = "insumo_producto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producto_id: Mapped[int] = mapped_column(Integer, index=True)
    insumo_floral_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    insumo_no_floral_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cantidad_consumida: Mapped[int] = mapped_column(Integer, default=1)
