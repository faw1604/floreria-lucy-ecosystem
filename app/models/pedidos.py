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
    # Nuevo / esperando_validacion / Pendiente pago / comprobante_recibido / pagado
    # En producción / Listo / En camino / Entregado / Cancelado / rechazado
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
    estado_florista: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # pendiente_aprobacion / aprobado / aprobado_con_modificacion / cambio_sugerido / rechazado
    nota_florista: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inicio_ruta_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    entregado_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    foto_entrega_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intento_fallido_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nota_no_entrega: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ruta: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    repartidor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    metodo_entrega: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # mostrador | recoger | envio | funeral_envio | funeral_recoger
    modo_fecha_fuerte_lote: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    listo_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    produccion_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelado_razon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Campos flujo WhatsApp
    comprobante_pago_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comprobante_pago_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pago_confirmado_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pago_confirmado_por: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ticket_enviado_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nota_validacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tracking_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    requiere_factura: Mapped[bool] = mapped_column(Boolean, default=False)
    facturado: Mapped[bool] = mapped_column(Boolean, default=False)
    folio_fiscal: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    datos_fiscales_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class ItemPedido(Base):
    __tablename__ = "items_pedido"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[int] = mapped_column(Integer, index=True)
    producto_id: Mapped[int] = mapped_column(Integer, index=True)
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    precio_unitario: Mapped[int] = mapped_column(Integer)  # en centavos
    es_personalizado: Mapped[bool] = mapped_column(Boolean, default=False)
    nombre_personalizado: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NotificacionLog(Base):
    __tablename__ = "notificaciones_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(String(30))  # Confirmación / Listo / En camino / Entregado
    mensaje: Mapped[str] = mapped_column(Text)
    enviado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    entregado: Mapped[bool] = mapped_column(Boolean, default=False)
