from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    tipo: Mapped[str] = mapped_column(String(20), default="normal")  # normal | funeral
    orden: Mapped[int] = mapped_column(Integer, default=0)


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    nombre: Mapped[str] = mapped_column(String(200), index=True)
    categoria: Mapped[str] = mapped_column(String(100))
    precio: Mapped[int] = mapped_column(Integer)  # en centavos
    costo: Mapped[int] = mapped_column(Integer, default=0)  # en centavos
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    disponible_hoy: Mapped[bool] = mapped_column(Boolean, default=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    imagen_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    precio_descuento: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    etiquetas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dimensiones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visible_catalogo: Mapped[bool] = mapped_column(Boolean, default=True)
    stock_activo: Mapped[bool] = mapped_column(Boolean, default=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    medida_alto: Mapped[Optional[float]] = mapped_column(Numeric(6, 1), nullable=True)
    medida_ancho: Mapped[Optional[float]] = mapped_column(Numeric(6, 1), nullable=True)
    costo_unitario: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    destacado: Mapped[bool] = mapped_column(Boolean, default=False)
    vender_por_fraccion: Mapped[bool] = mapped_column(Boolean, default=False)
    imagenes_extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array de URLs


class ProductoVariante(Base):
    __tablename__ = "producto_variantes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    producto_id: Mapped[int] = mapped_column(Integer, ForeignKey("productos.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # color | tamaño | estilo
    nombre: Mapped[str] = mapped_column(String(100))
    codigo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    imagen_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    precio: Mapped[int] = mapped_column(Integer)  # centavos
    precio_descuento: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stock_activo: Mapped[bool] = mapped_column(Boolean, default=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
