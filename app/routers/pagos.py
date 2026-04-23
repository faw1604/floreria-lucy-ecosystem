from fastapi import APIRouter, Depends, HTTPException, Cookie, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.pagos import MetodoPago
from app.models.pedidos import Pedido
from app.routers.auth import verificar_sesion
from app.core import mp_client
import logging

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


@router.post("/mp/preference/{pedido_id}")
async def crear_mp_preference(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Crea una preference de MercadoPago para un pedido (Checkout Pro).

    Solo accesible con sesión autenticada (operador POS o admin). El cliente
    final NO llama este endpoint — recibe el link ya generado por WhatsApp
    cuando el operador presiona 'Enviar ticket' en el POS.
    """
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")

    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
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
        track_link = f'<a href="/seguimiento/{tracking_token}" class="btn">📦 Ver mi pedido</a>'
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
