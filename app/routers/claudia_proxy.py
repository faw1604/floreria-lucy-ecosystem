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


def _auth(panel_session):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")


def _headers() -> dict:
    """Headers para autenticar con el agentkit."""
    h = {"Content-Type": "application/json"}
    if AGENTKIT_API_KEY:
        h["X-Admin-Key"] = AGENTKIT_API_KEY
    return h


@router.get("/chats")
async def claudia_chats(panel_session: str | None = Cookie(default=None)):
    """Lista chats activos desde el agentkit."""
    _auth(panel_session)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{AGENTKIT_URL}/chats-activos", headers=_headers())
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Error al obtener chats")
        return r.json()


@router.post("/bloquear")
async def claudia_bloquear(request: Request, panel_session: str | None = Cookie(default=None)):
    """Bloquea chat para intervención humana."""
    _auth(panel_session)
    data = await request.json()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{AGENTKIT_URL}/bloquear-chat", json=data, headers=_headers())
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Error al bloquear chat")
        return r.json()


@router.post("/liberar")
async def claudia_liberar(request: Request, panel_session: str | None = Cookie(default=None)):
    """Libera chat de vuelta a Claudia."""
    _auth(panel_session)
    data = await request.json()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{AGENTKIT_URL}/liberar-chat", json=data, headers=_headers())
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Error al liberar chat")
        return r.json()


@router.get("/historial/{telefono}")
async def claudia_historial(telefono: str, limite: int = 50, panel_session: str | None = Cookie(default=None)):
    """Obtiene historial de conversación."""
    _auth(panel_session)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{AGENTKIT_URL}/historial-chat/{telefono}",
            params={"limite": limite},
            headers=_headers(),
        )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Error al obtener historial")
        return r.json()


@router.post("/enviar-mensaje")
async def claudia_enviar_mensaje(request: Request, panel_session: str | None = Cookie(default=None)):
    """Envía mensaje de WhatsApp en nombre del humano."""
    _auth(panel_session)
    data = await request.json()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{AGENTKIT_URL}/enviar-mensaje-humano", json=data, headers=_headers())
        if r.status_code != 200:
            detail = "Error al enviar mensaje"
            try:
                detail = r.json().get("detail", detail)
            except Exception:
                pass
            raise HTTPException(status_code=r.status_code, detail=detail)
        return r.json()


@router.get("/notas/{telefono}")
async def claudia_notas(telefono: str, panel_session: str | None = Cookie(default=None)):
    """Obtiene notas internas de un chat."""
    _auth(panel_session)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{AGENTKIT_URL}/notas-chat/{telefono}", headers=_headers())
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Error al obtener notas")
        return r.json()


@router.post("/notas")
async def claudia_guardar_nota(request: Request, panel_session: str | None = Cookie(default=None)):
    """Guarda nota interna para un chat."""
    _auth(panel_session)
    data = await request.json()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{AGENTKIT_URL}/notas-chat", json=data, headers=_headers())
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Error al guardar nota")
        return r.json()


@router.delete("/notas/{nota_id}")
async def claudia_eliminar_nota(nota_id: int, panel_session: str | None = Cookie(default=None)):
    """Elimina nota interna."""
    _auth(panel_session)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(f"{AGENTKIT_URL}/notas-chat/{nota_id}", headers=_headers())
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Error al eliminar nota")
        return r.json()
