"""
Estados centralizados del sistema Florería Lucy.
Importar desde aquí en vez de hardcodear strings.
"""


# ─── Estados del pedido ───
class EstadoPedido:
    NUEVO = "Nuevo"
    ESPERANDO_VALIDACION = "esperando_validacion"
    PENDIENTE_PAGO = "Pendiente pago"
    COMPROBANTE_RECIBIDO = "comprobante_recibido"
    PAGADO = "pagado"
    EN_PRODUCCION = "En producción"
    LISTO = "Listo"
    LISTO_TALLER = "listo_taller"
    EN_CAMINO = "En camino"
    ENTREGADO = "Entregado"
    CANCELADO = "Cancelado"
    INTENTO_FALLIDO = "intento_fallido"

    # Agrupaciones útiles para queries
    ACTIVOS = [ESPERANDO_VALIDACION, PENDIENTE_PAGO, COMPROBANTE_RECIBIDO,
               PAGADO, EN_PRODUCCION, LISTO, LISTO_TALLER, EN_CAMINO]
    FINALIZADOS = [ENTREGADO, CANCELADO]
    EN_TALLER_NUEVOS = [ESPERANDO_VALIDACION, PENDIENTE_PAGO]
    EN_TALLER_PRODUCCION = [EN_PRODUCCION, PAGADO]
    LISTOS = [LISTO, LISTO_TALLER]
    VENTA_COMPLETADA = [LISTO, LISTO_TALLER, EN_PRODUCCION, PAGADO, EN_CAMINO, ENTREGADO]


# ─── Estados del florista ───
class EstadoFlorista:
    PENDIENTE = "pendiente_aprobacion"
    APROBADO = "aprobado"
    APROBADO_CON_MODIFICACION = "aprobado_con_modificacion"
    CAMBIO_SUGERIDO = "cambio_sugerido"
    RECHAZADO = "rechazado"
    REQUIERE_ATENCION = "requiere_atencion"
    PENDIENTE_PAGO = "pendiente_pago"

    # Los que aparecen en pestaña Nuevos del taller
    VISIBLES_EN_NUEVOS = [None, PENDIENTE, APROBADO_CON_MODIFICACION,
                          CAMBIO_SUGERIDO, RECHAZADO, REQUIERE_ATENCION]


# ─── Métodos de entrega ───
class MetodoEntrega:
    MOSTRADOR = "mostrador"
    RECOGER = "recoger"
    ENVIO = "envio"
    FUNERAL_ENVIO = "funeral_envio"
    FUNERAL_RECOGER = "funeral_recoger"

    PARA_RECOGER = [RECOGER, FUNERAL_RECOGER]
    PARA_ENVIO = [ENVIO, FUNERAL_ENVIO]


# ─── Canales ───
class Canal:
    WHATSAPP = "WhatsApp"
    MOSTRADOR = "Mostrador"
    WEB = "Web"


# ─── Estados de reserva ───
class EstadoReserva:
    DISPONIBLE = "disponible"
    VENDIDA = "vendida"
    DESCARTADA = "descartada"
