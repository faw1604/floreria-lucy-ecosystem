# app/routers/claudia_proxy.py — Proxy al servicio whatsapp-agentkit
"""
Reenvía requests del panel admin al servicio de Claudia (whatsapp-agentkit)
autenticando con X-Admin-Key header.
"""
import os
import logging
from fastapi import APIRouter, Request, HTTPException, Cookie
from app.routers.auth import verificar_sesion
import httpx

logger = logging.getLogger("floreria")

router = APIRouter()

AGENTKIT_URL = os.getenv("AGENTKIT_URL", "https://whatsapp-agentkit-production-4e69.up.railway.app")
AGENTKIT_API_KEY = os.getenv("AGENTKIT_API_KEY", "")

logger.info(f"[CLAUDIA PROXY] URL={AGENTKIT_URL}, API_KEY={'SET' if AGENTKIT_API_KEY else 'EMPTY'}")


def _auth(panel_session):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")


def _headers() -> dict:
    """Headers para autenticar con el agentkit."""
    h = {"Content-Type": "application/json"}
    if AGENTKIT_API_KEY:
        h["X-Admin-Key"] = AGENTKIT_API_KEY
    return h


async def _proxy_get(url, params=None):
    """GET request al agentkit con manejo de errores."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=_headers(), params=params)
            if r.status_code != 200:
                logger.error(f"[CLAUDIA PROXY] GET {url} → {r.status_code}: {r.text[:200]}")
                raise HTTPException(status_code=r.status_code, detail=f"Agentkit error: {r.status_code}")
            return r.json()
    except httpx.HTTPError as e:
        logger.error(f"[CLAUDIA PROXY] GET {url} → httpx error: {e}")
        raise HTTPException(status_code=502, detail=f"Error conectando al agentkit: {e}")


async def _proxy_post(url, data):
    """POST request al agentkit con manejo de errores."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=data, headers=_headers())
            if r.status_code != 200:
                logger.error(f"[CLAUDIA PROXY] POST {url} → {r.status_code}: {r.text[:200]}")
                detail = "Error del agentkit"
                try:
                    detail = r.json().get("detail", detail)
                except Exception:
                    pass
                raise HTTPException(status_code=r.status_code, detail=detail)
            return r.json()
    except httpx.HTTPError as e:
        logger.error(f"[CLAUDIA PROXY] POST {url} → httpx error: {e}")
        raise HTTPException(status_code=502, detail=f"Error conectando al agentkit: {e}")


async def _proxy_delete(url):
    """DELETE request al agentkit con manejo de errores."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.delete(url, headers=_headers())
            if r.status_code != 200:
                logger.error(f"[CLAUDIA PROXY] DELETE {url} → {r.status_code}: {r.text[:200]}")
                raise HTTPException(status_code=r.status_code, detail=f"Agentkit error: {r.status_code}")
            return r.json()
    except httpx.HTTPError as e:
        logger.error(f"[CLAUDIA PROXY] DELETE {url} → httpx error: {e}")
        raise HTTPException(status_code=502, detail=f"Error conectando al agentkit: {e}")


@router.get("/chats")
async def claudia_chats(panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_get(f"{AGENTKIT_URL}/chats-activos")


@router.post("/bloquear")
async def claudia_bloquear(request: Request, panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_post(f"{AGENTKIT_URL}/bloquear-chat", await request.json())


@router.post("/liberar")
async def claudia_liberar(request: Request, panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_post(f"{AGENTKIT_URL}/liberar-chat", await request.json())


@router.get("/historial/{telefono}")
async def claudia_historial(telefono: str, limite: int = 50, panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_get(f"{AGENTKIT_URL}/historial-chat/{telefono}", params={"limite": limite})


@router.post("/enviar-mensaje")
async def claudia_enviar_mensaje(request: Request, panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_post(f"{AGENTKIT_URL}/enviar-mensaje-humano", await request.json())


@router.post("/enviar-catalogo")
async def claudia_enviar_catalogo(request: Request, panel_session: str | None = Cookie(default=None)):
    """Envía mensaje como Claudia (sin bloquear chat). Para catálogos, etc."""
    _auth(panel_session)
    return await _proxy_post(f"{AGENTKIT_URL}/enviar-mensaje-claudia", await request.json())


@router.get("/notas/{telefono}")
async def claudia_notas(telefono: str, panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_get(f"{AGENTKIT_URL}/notas-chat/{telefono}")


@router.post("/notas")
async def claudia_guardar_nota(request: Request, panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_post(f"{AGENTKIT_URL}/notas-chat", await request.json())


@router.delete("/notas/{nota_id}")
async def claudia_eliminar_nota(nota_id: int, panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_delete(f"{AGENTKIT_URL}/notas-chat/{nota_id}")


@router.delete("/historial/{telefono}")
async def claudia_limpiar_historial(telefono: str, panel_session: str | None = Cookie(default=None)):
    _auth(panel_session)
    return await _proxy_delete(f"{AGENTKIT_URL}/historial-chat/{telefono}")
