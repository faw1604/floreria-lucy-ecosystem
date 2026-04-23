"""Cliente HTTP para MercadoPago (no usa SDK — solo httpx).

Lee credenciales de env vars:
- MP_ACCESS_TOKEN: secreto, server-side (TEST-... sandbox o APP_USR-... prod)
- MP_PUBLIC_KEY: para frontend, no se usa aquí pero se expone vía endpoint
- MP_WEBHOOK_SECRET: opcional, para validar firma del webhook (se setea en panel MP)
"""
import os
import hmac
import hashlib
import httpx
from typing import Any

MP_BASE = "https://api.mercadopago.com"


def _access_token() -> str:
    tok = os.getenv("MP_ACCESS_TOKEN", "").strip()
    if not tok:
        raise RuntimeError("MP_ACCESS_TOKEN no configurado en env vars")
    return tok


def _is_sandbox() -> bool:
    return _access_token().startswith("TEST-") or "test" in os.getenv("MP_MODE", "").lower()


async def crear_preference(
    pedido_folio: str,
    total_centavos: int,
    descripcion: str,
    cliente_email: str | None = None,
    success_url: str | None = None,
    failure_url: str | None = None,
    pending_url: str | None = None,
    notification_url: str | None = None,
) -> dict[str, Any]:
    """Crea una preference de checkout en MP.

    Devuelve el dict completo. Los campos clave:
    - id: preference_id
    - init_point: URL de checkout en producción
    - sandbox_init_point: URL de checkout en sandbox
    """
    body = {
        "items": [{
            "id": pedido_folio,
            "title": descripcion[:250],  # MP limita a 256 chars
            "quantity": 1,
            "currency_id": "MXN",
            "unit_price": round(total_centavos / 100, 2),
        }],
        "external_reference": pedido_folio,
        "statement_descriptor": "FLORERIA LUCY",
    }
    if cliente_email:
        body["payer"] = {"email": cliente_email}
    back_urls = {}
    if success_url:
        back_urls["success"] = success_url
    if failure_url:
        back_urls["failure"] = failure_url
    if pending_url:
        back_urls["pending"] = pending_url
    if back_urls:
        body["back_urls"] = back_urls
        body["auto_return"] = "approved"
    if notification_url:
        body["notification_url"] = notification_url

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{MP_BASE}/checkout/preferences",
            headers={
                "Authorization": f"Bearer {_access_token()}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if r.status_code >= 400:
            # Bubble up el body de MP para debug (incluye el motivo real del error)
            raise RuntimeError(f"MP {r.status_code}: {r.text}")
        return r.json()


async def obtener_pago(payment_id: str) -> dict[str, Any]:
    """Obtiene el detalle de un pago (para verificar status en el webhook)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{MP_BASE}/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {_access_token()}"},
        )
        r.raise_for_status()
        return r.json()


def verificar_firma_webhook(payload_raw: bytes, signature_header: str | None,
                             request_id: str | None, data_id: str | None) -> bool:
    """Verifica la firma HMAC de un webhook de MP.

    Formato del header `x-signature`: "ts=TIMESTAMP,v1=HASH_HEX"
    Plantilla del hash: "id:{data_id};request-id:{request_id};ts:{ts};"
    Hash: HMAC-SHA256(secret, template) en hex

    Si MP_WEBHOOK_SECRET no está configurado, devuelve True (sin validación).
    En producción el secret DEBE configurarse para seguridad.
    """
    secret = os.getenv("MP_WEBHOOK_SECRET", "").strip()
    if not secret:
        # Sin secret configurado — skip validación (se registra warning desde el caller)
        return True
    if not signature_header:
        return False
    # Parse header "ts=123,v1=abcdef"
    parts = {}
    for p in signature_header.split(","):
        if "=" in p:
            k, v = p.strip().split("=", 1)
            parts[k.strip()] = v.strip()
    ts = parts.get("ts")
    v1 = parts.get("v1")
    if not ts or not v1:
        return False
    # Construir plantilla y calcular hash
    template = f"id:{data_id or ''};request-id:{request_id or ''};ts:{ts};"
    expected = hmac.new(secret.encode(), template.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)
