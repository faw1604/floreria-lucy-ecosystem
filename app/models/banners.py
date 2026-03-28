from sqlalchemy import String, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class BannerCatalogo(Base):
    __tablename__ = "banners_catalogo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imagen_url: Mapped[str] = mapped_column(Text)
    titulo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    subtitulo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
