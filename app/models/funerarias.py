from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from typing import Optional

class Funeraria(Base):
    __tablename__ = "funerarias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(200), index=True)
    aliases: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array de nombres alternativos
    direccion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zona: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Morada / Azul / Verde
    costo_envio: Mapped[int] = mapped_column(Integer, default=9900)  # en centavos — default $99
