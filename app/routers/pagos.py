from fastapi import APIRouter, Depends, HTTPException, Cookie, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.pagos import MetodoPago
from app.models.pedidos import Pedido
from app.models.clientes import Cliente
from app.routers.auth import verificar_sesion
from app.core import mp_client
import logging
import os

router = APIRouter()
log = logging.getLogger("floreria.pagos")

@router.get("/cuenta-activa")
async def get_cuenta_activa(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MetodoPago)
        .where(MetodoPago.tipo == "transferencia")
        .where(MetodoPago.activo == True)
        .limit(1)
    )
    cuenta = result.scalar_one_or_none()
    if not cuenta:
        raise HTTPException(status_code=404, detail="No hay cuenta activa para transferencia")
    return {"banco": cuenta.banco, "titular": cuenta.titular, "clabe": cuenta.clabe}

@router.get("/oxxo")
async def get_datos_oxxo(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MetodoPago)
        .where(MetodoPago.tipo == "oxxo")
        .where(MetodoPago.activo == True)
        .limit(1)
    )
    oxxo = result.scalar_one_or_none()
    if not oxxo:
        raise HTTPException(status_code=404, detail="No hay datos OXXO configurados")
    return {"numero_tarjeta": oxxo.numero_tarjeta, "titular": oxxo.titular}

@router.get("/")
async def listar_metodos(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(MetodoPago))
    metodos = result.scalars().all()
    return [{"id": m.id, "tipo": m.tipo, "banco": m.banco, "titular": m.titular, "activo": m.activo, "solo_sucursal": m.solo_sucursal} for m in metodos]

@router.patch("/{metodo_id}/activar")
async def activar_metodo(
    metodo_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(MetodoPago).where(MetodoPago.id == metodo_id))
    metodo = result.scalar_one_or_none()
    if not metodo:
        raise HTTPException(status_code=404, detail="Método no encontrado")
    if metodo.tipo == "transferencia":
        await db.execute(
            select(MetodoPago).where(MetodoPago.tipo == "transferencia")
        )
        all_result = await db.execute(select(MetodoPago).where(MetodoPago.tipo == "transferencia"))
        for m in all_result.scalars().all():
            m.activo = False
    metodo.activo = request.get("activo", True)
    await db.commit()
    return {"id": metodo.id, "activo": metodo.activo}

@router.post("/")
async def crear_metodo(
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    metodo = MetodoPago(
        tipo=request.get("tipo", "transferencia"),
        banco=request.get("banco"),
        titular=request.get("titular"),
        clabe=request.get("clabe"),
        numero_tarjeta=request.get("numero_tarjeta"),
        activo=request.get("activo", True),
        solo_sucursal=request.get("solo_sucursal", False),
    )
    db.add(metodo)
    await db.commit()
    await db.refresh(metodo)
    return {"id": metodo.id, "tipo": metodo.tipo}


# ═══════════════════════════════════════════════════════════════════════
# MERCADOPAGO — Checkout Pro (Link de pago)
# ═══════════════════════════════════════════════════════════════════════

def _base_url(request: Request) -> str:
    """URL base del sitio respetando proxies (Railway usa x-forwarded-*)."""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    return f"{proto}://{host}"


@router.post("/mp/preference/{pedido_ref}")
async def crear_mp_preference(
    pedido_ref: str,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Crea una preference de MercadoPago para un pedido (Checkout Pro).

    Acepta tanto el ID numérico como el folio (ej. 12 o FL-2026-5158).

    Solo accesible con sesión autenticada (operador POS o admin). El cliente
    final NO llama este endpoint — recibe el link ya generado por WhatsApp
    cuando el operador presiona 'Enviar ticket' en el POS.
    """
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")

    # Resolver pedido por id numérico o por numero (folio)
    pedido = None
    if pedido_ref.isdigit():
        result = await db.execute(select(Pedido).where(Pedido.id == int(pedido_ref)))
        pedido = result.scalar_one_or_none()
    if not pedido:
        result = await db.execute(select(Pedido).where(Pedido.numero == pedido_ref))
        pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    total = int(pedido.total or 0)
    if total <= 0:
        raise HTTPException(status_code=400, detail="Pedido sin total válido")

    descripcion = f"Pedido {pedido.numero} - Florería Lucy"
    base = _base_url(request)
    tracking = pedido.tracking_token or ""

    # MP no acepta back_urls/notification_url con localhost — solo URLs públicas.
    # En desarrollo local omitimos esos parámetros (el flujo manual de copiar el
    # link y abrirlo sigue funcionando; webhook se configura desde panel MP en prod).
    is_localhost = "localhost" in base or "127.0.0.1" in base
    success_url = failure_url = pending_url = webhook_url = None
    if not is_localhost:
        success_url = f"{base}/pagos/exito?token={tracking}" if tracking else f"{base}/pagos/exito"
        failure_url = f"{base}/pagos/fallido?token={tracking}" if tracking else f"{base}/pagos/fallido"
        pending_url = f"{base}/pagos/pendiente?token={tracking}" if tracking else f"{base}/pagos/pendiente"
        webhook_url = f"{base}/pagos/mp/webhook"

    try:
        pref = await mp_client.crear_preference(
            pedido_folio=pedido.numero,
            total_centavos=total,
            descripcion=descripcion,
            cliente_email=getattr(pedido, "cliente_email", None) or None,
            success_url=success_url,
            failure_url=failure_url,
            pending_url=pending_url,
            notification_url=webhook_url,
        )
    except RuntimeError as e:
        log.error(f"MP no configurado: {e}")
        raise HTTPException(status_code=503, detail=f"MercadoPago no configurado: {e}")
    except Exception as e:
        log.error(f"Error MP preference para pedido {pedido_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Error MercadoPago: {e}")

    is_sandbox = mp_client._is_sandbox()
    link = pref.get("sandbox_init_point") if is_sandbox else pref.get("init_point")

    return {
        "ok": True,
        "preference_id": pref.get("id"),
        "link": link,
        "sandbox": is_sandbox,
    }


# ─── Páginas de retorno (las visita el cliente tras pagar en MP) ────────────

_PAGE_CSS = """<style>
body{margin:0;padding:0;font-family:'Inter',sans-serif;background:#faf8f5;color:#1a1a1a;
     min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#fff;border-radius:20px;padding:48px 32px;max-width:480px;width:90%;
      text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.08)}
.icon{font-size:64px;margin-bottom:16px}
h1{font-family:'Playfair Display',serif;color:#193a2c;font-size:28px;margin:0 0 12px}
p{color:#555;line-height:1.5;font-size:15px;margin:0 0 20px}
.btn{display:inline-block;padding:14px 28px;background:#193a2c;color:#faf8f5;
     border-radius:12px;text-decoration:none;font-weight:600;font-size:14px;margin:4px}
.btn-sec{background:transparent;color:#193a2c;border:2px solid #193a2c}
</style>"""


def _render_pago_page(icon: str, titulo: str, mensaje: str, tracking_token: str | None,
                      btn_label: str = "Volver al catálogo", btn_url: str = "/catalogo/") -> str:
    track_link = ""
    if tracking_token:
        track_link = f'<a href="/catalogo/seguimiento.html?token={tracking_token}" class="btn">📦 Ver mi pedido</a>'
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo} — Florería Lucy</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
{_PAGE_CSS}
</head><body>
<div class="card">
  <div class="icon">{icon}</div>
  <h1>{titulo}</h1>
  <p>{mensaje}</p>
  {track_link}
  <a href="{btn_url}" class="btn btn-sec">{btn_label}</a>
</div>
</body></html>"""


@router.get("/exito", response_class=HTMLResponse)
async def pago_exito(token: str | None = None):
    return HTMLResponse(_render_pago_page(
        icon="✅",
        titulo="¡Pago recibido!",
        mensaje="Tu pedido ya está pagado. Te enviaremos confirmación por WhatsApp y "
                "podrás seguir el estado de tu pedido en cualquier momento.",
        tracking_token=token,
    ))


@router.get("/fallido", response_class=HTMLResponse)
async def pago_fallido(token: str | None = None):
    return HTMLResponse(_render_pago_page(
        icon="❌",
        titulo="Pago no completado",
        mensaje="Hubo un problema con tu pago. No te preocupes, no se realizó ningún cargo. "
                "Puedes intentar de nuevo desde el link que recibiste por WhatsApp.",
        tracking_token=token,
        btn_label="Contactar por WhatsApp",
        btn_url="https://wa.me/5216143349392",
    ))


@router.get("/pendiente", response_class=HTMLResponse)
async def pago_pendiente(token: str | None = None):
    return HTMLResponse(_render_pago_page(
        icon="⏳",
        titulo="Pago en proceso",
        mensaje="Tu pago está siendo procesado. Te notificaremos por WhatsApp en cuanto se confirme.",
        tracking_token=token,
    ))


@router.post("/mp/webhook")
async def mp_webhook(request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Recibe notificaciones de MercadoPago cuando cambia el estado de un pago.

    MP manda body como:
      {"id": "webhook_id", "action": "payment.created|payment.updated",
       "data": {"id": "payment_id"}, ...}

    Flujo:
    1. Valida firma HMAC si MP_WEBHOOK_SECRET está configurado
    2. Si es evento de pago, obtiene detalle del pago vía API MP
    3. Si status=approved → marca el pedido como PAGADO (idempotente)
    4. Siempre responde 200 (MP reintenta si recibe no-200)
    """
    # Leer body crudo (necesario para validar firma)
    payload_raw = await request.body()
    try:
        import json as _json
        payload = _json.loads(payload_raw) if payload_raw else {}
    except Exception:
        log.warning("MP webhook: body inválido")
        return {"ok": True}  # 200 para no causar retries de MP

    # Extraer identificadores para firma
    signature = request.headers.get("x-signature")
    request_id = request.headers.get("x-request-id")
    # IMPORTANTE: MP usa el data.id del query string para la firma (no el del body).
    # Si solo viene en body, se intenta con eso.
    data_id_qs = request.query_params.get("data.id")
    data_id_body = (payload.get("data") or {}).get("id")
    data_id = data_id_qs or data_id_body

    log.info(f"MP webhook recibido: data_id_qs={data_id_qs} data_id_body={data_id_body} sig={'sí' if signature else 'no'}")

    # Validar firma (si no está configurado secret, skip con warning).
    # IMPORTANTE: aunque la firma falle, NO rechazamos el evento — solo lo logueamos.
    # El spec de MP cambia y a veces la firma no coincide por diferencias en
    # codificación/orden. Con event válido + status approved en MP API es seguro confirmar.
    if not os.getenv("MP_WEBHOOK_SECRET"):
        log.warning("MP webhook recibido sin MP_WEBHOOK_SECRET configurado — saltando validación firma")
    else:
        # Probar firma con id de qs y de body por separado
        sig_ok = mp_client.verificar_firma_webhook(payload_raw, signature, request_id,
                                                    str(data_id_qs) if data_id_qs else None)
        if not sig_ok and data_id_body:
            sig_ok = mp_client.verificar_firma_webhook(payload_raw, signature, request_id, str(data_id_body))
        if not sig_ok:
            log.warning(f"MP webhook firma no validó (id_qs={data_id_qs}, id_body={data_id_body}, req={request_id}) — continuando con verificación vía API MP")
        else:
            log.info(f"MP webhook firma OK (id={data_id})")

    # Solo procesamos eventos tipo payment
    topic = payload.get("type") or payload.get("topic") or ""
    action = payload.get("action") or ""
    is_payment = topic == "payment" or action.startswith("payment.")
    if not is_payment or not data_id:
        log.info(f"MP webhook ignorado (topic={topic}, action={action}, data_id={data_id})")
        return {"ok": True}

    # Obtener detalles del pago
    try:
        pago = await mp_client.obtener_pago(str(data_id))
    except Exception as e:
        log.error(f"MP webhook: error obteniendo pago {data_id}: {e}")
        return {"ok": True}

    status = pago.get("status")
    external_ref = pago.get("external_reference")  # nuestro pedido.numero
    log.info(f"MP webhook: pago {data_id} status={status} ref={external_ref}")

    if status != "approved" or not external_ref:
        # Solo procesamos pagos aprobados con referencia a un pedido
        return {"ok": True}

    # Buscar pedido por numero (external_reference)
    result = await db.execute(select(Pedido).where(Pedido.numero == external_ref))
    pedido = result.scalar_one_or_none()
    if not pedido:
        log.warning(f"MP webhook: pedido {external_ref} no encontrado")
        return {"ok": True}

    # Idempotencia: si ya está marcado como pagado, no hacer nada
    if pedido.pago_confirmado:
        log.info(f"MP webhook: pedido {external_ref} ya estaba pagado, skip")
        return {"ok": True}

    # Marcar como pagado
    from app.core.estados import EstadoPedido as EP
    from app.core.utils import ahora
    pedido.pago_confirmado = True
    pedido.pago_confirmado_at = ahora()
    pedido.pago_confirmado_por = "MercadoPago"
    # Solo cambiar estado si aún no ha pasado de pendiente_pago (el taller pudo haber avanzado)
    if pedido.estado in [EP.PENDIENTE_PAGO, EP.ESPERANDO_VALIDACION, EP.COMPROBANTE_RECIBIDO]:
        pedido.estado = EP.PAGADO
    await db.commit()
    log.info(f"MP webhook: pedido {external_ref} marcado como PAGADO (payment_id={data_id})")

    # Enviar WhatsApp de confirmación de pago al cliente.
    # Mismo patrón que pos_finalizar_pedido (pos.py:1278): usa BackgroundTasks
    # para no bloquear la respuesta y porque MP reintenta si tarda demasiado.
    if pedido.tracking_token and pedido.customer_id:
        try:
            cliente_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cliente = cliente_result.scalar_one_or_none()
            if cliente and cliente.telefono:
                tracking_url = f"https://www.florerialucy.com/catalogo/seguimiento.html?token={pedido.tracking_token}"
                from app.routers.catalogo import _enviar_whatsapp
                _tel_wa = cliente.telefono
                _nombre_wa = cliente.nombre.split()[0] if cliente.nombre else "amig@"
                _msg_wa = (
                    f"Hola {_nombre_wa} 🌸\n\n"
                    f"Tu pago para el pedido {pedido.numero} fue confirmado! Tu arreglo sera elaborado pronto.\n\n"
                    f"Sigue el estatus aqui:\n{tracking_url}"
                )
                async def _send_wa(tel, msg, folio):
                    try:
                        await _enviar_whatsapp(tel, msg)
                        log.info(f"[MP WEBHOOK] WhatsApp pago confirmado enviado a {tel} para {folio}")
                    except Exception as wa_err:
                        log.error(f"[MP WEBHOOK] Error enviando WhatsApp para {folio}: {wa_err}")
                background_tasks.add_task(_send_wa, _tel_wa, _msg_wa, pedido.numero)
        except Exception as e:
            log.error(f"[MP WEBHOOK] Error preparando WhatsApp para {external_ref}: {e}")

    return {"ok": True}


@router.get("/mp/webhook")
async def mp_webhook_get():
    """MP a veces hace GET para verificar que el endpoint existe (health check)."""
    return {"ok": True}


@router.post("/mp/reconciliar/{pedido_ref}")
async def mp_reconciliar_pedido(
    pedido_ref: str,
    background_tasks: BackgroundTasks,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Recuperar manualmente un pedido cuyo webhook MP no llegó.

    Consulta MP por external_reference (folio del pedido), busca el pago
    aprobado más reciente, y aplica la misma lógica que el webhook.

    Útil cuando:
    - MP falló al llamar el webhook
    - La firma rechazó el webhook
    - Operador quiere confirmar manualmente que un pago llegó
    """
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")

    # Resolver pedido por id numérico o por numero (folio)
    pedido = None
    if pedido_ref.isdigit():
        result = await db.execute(select(Pedido).where(Pedido.id == int(pedido_ref)))
        pedido = result.scalar_one_or_none()
    if not pedido:
        result = await db.execute(select(Pedido).where(Pedido.numero == pedido_ref))
        pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Consultar MP: search payments by external_reference
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{mp_client.MP_BASE}/v1/payments/search",
                headers={"Authorization": f"Bearer {mp_client._access_token()}"},
                params={"external_reference": pedido.numero, "sort": "date_created", "criteria": "desc"},
            )
            if r.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"MP search error: {r.text}")
            data = r.json()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"MercadoPago no configurado: {e}")
    except Exception as e:
        log.error(f"MP reconciliar: error consultando pagos para {pedido.numero}: {e}")
        raise HTTPException(status_code=502, detail=f"Error consultando MercadoPago: {e}")

    pagos = data.get("results") or []
    if not pagos:
        return {"ok": False, "encontrado": False, "mensaje": f"Sin pagos registrados en MP para {pedido.numero}"}

    # Buscar primer pago aprobado
    pago_aprobado = next((p for p in pagos if p.get("status") == "approved"), None)
    if not pago_aprobado:
        statuses = [p.get("status") for p in pagos]
        return {
            "ok": False,
            "encontrado": True,
            "aprobado": False,
            "mensaje": f"Pagos encontrados pero ninguno aprobado. Estados: {statuses}",
        }

    # Idempotencia
    if pedido.pago_confirmado:
        return {"ok": True, "ya_estaba_pagado": True, "payment_id": pago_aprobado.get("id")}

    # Marcar como pagado (misma lógica que webhook)
    from app.core.estados import EstadoPedido as EP
    from app.core.utils import ahora
    pedido.pago_confirmado = True
    pedido.pago_confirmado_at = ahora()
    pedido.pago_confirmado_por = "MercadoPago (reconciliado)"
    if pedido.estado in [EP.PENDIENTE_PAGO, EP.ESPERANDO_VALIDACION, EP.COMPROBANTE_RECIBIDO]:
        pedido.estado = EP.PAGADO
    await db.commit()
    log.info(f"MP reconciliar: pedido {pedido.numero} marcado PAGADO (payment_id={pago_aprobado.get('id')})")

    # Enviar WhatsApp de confirmación al cliente (mismo patrón que webhook).
    if pedido.tracking_token and pedido.customer_id:
        try:
            cliente_result = await db.execute(select(Cliente).where(Cliente.id == pedido.customer_id))
            cliente = cliente_result.scalar_one_or_none()
            if cliente and cliente.telefono:
                tracking_url = f"https://www.florerialucy.com/catalogo/seguimiento.html?token={pedido.tracking_token}"
                from app.routers.catalogo import _enviar_whatsapp
                _tel_wa = cliente.telefono
                _nombre_wa = cliente.nombre.split()[0] if cliente.nombre else "amig@"
                _msg_wa = (
                    f"Hola {_nombre_wa} 🌸\n\n"
                    f"Tu pago para el pedido {pedido.numero} fue confirmado! Tu arreglo sera elaborado pronto.\n\n"
                    f"Sigue el estatus aqui:\n{tracking_url}"
                )
                async def _send_wa(tel, msg, folio):
                    try:
                        await _enviar_whatsapp(tel, msg)
                        log.info(f"[MP RECONCILIAR] WhatsApp pago confirmado enviado a {tel} para {folio}")
                    except Exception as wa_err:
                        log.error(f"[MP RECONCILIAR] Error enviando WhatsApp para {folio}: {wa_err}")
                background_tasks.add_task(_send_wa, _tel_wa, _msg_wa, pedido.numero)
        except Exception as e:
            log.error(f"[MP RECONCILIAR] Error preparando WhatsApp para {pedido.numero}: {e}")

    return {
        "ok": True,
        "marcado_pagado": True,
        "payment_id": pago_aprobado.get("id"),
        "monto": pago_aprobado.get("transaction_amount"),
        "fecha": pago_aprobado.get("date_approved"),
    }
