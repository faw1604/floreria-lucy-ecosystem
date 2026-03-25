from sqlalchemy import String, Integer, Boolean, Text, DateTime, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date
from typing import Optional
from app.database import Base

class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # FL-2025-001
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    canal: Mapped[str] = mapped_column(String(20), default="WhatsApp")  # WhatsApp / Mostrador / Web
    estado: Mapped[str] = mapped_column(String(30), default="Nuevo")
    # Nuevo / En producción / Listo / En camino / Entregado / Pendiente pago / Cancelado
    fecha_pedido: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    fecha_entrega: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    horario_entrega: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # mañana/tarde/noche
    hora_exacta: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    zona_entrega: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    direccion_entrega: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    receptor_nombre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    receptor_telefono: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    dedicatoria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notas_internas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    forma_pago: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    pago_confirmado: Mapped[bool] = mapped_column(Boolean, default=False)
    subtotal: Mapped[int] = mapped_column(Integer, default=0)  # en centavos
    envio: Mapped[int] = mapped_column(Integer, default=0)  # en centavos
    total: Mapped[int] = mapped_column(Integer, default=0)  # en centavos
    requiere_humano: Mapped[bool] = mapped_column(Boolean, default=False)
    tipo_especial: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Funeral / Evento / Normal


class ItemPedido(Base):
    __tablename__ = "items_pedido"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[int] = mapped_column(Integer, index=True)
    producto_id: Mapped[int] = mapped_column(Integer, index=True)
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    precio_unitario: Mapped[int] = mapped_column(Integer)  # en centavos


class NotificacionLog(Base):
    __tablename__ = "notificaciones_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(String(30))  # Confirmación / Listo / En camino / Entregado
    mensaje: Mapped[str] = mapped_column(Text)
    enviado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    entregado: Mapped[bool] = mapped_column(Boolean, default=False)
