from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class DatosFiscalesCliente(Base):
    __tablename__ = "datos_fiscales_cliente"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rfc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    razon_social: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    regimen_fiscal: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    uso_cfdi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    correo_fiscal: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    codigo_postal: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
