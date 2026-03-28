from sqlalchemy import String, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class ConfiguracionNegocio(Base):
    __tablename__ = "configuracion_negocio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String(100), unique=True)
    valor: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class HorarioEspecifico(Base):
    __tablename__ = "horarios_especificos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dia_semana: Mapped[int] = mapped_column(Integer)  # 0=Lunes..6=Domingo
    hora: Mapped[str] = mapped_column(String(10))  # "13:00"
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
