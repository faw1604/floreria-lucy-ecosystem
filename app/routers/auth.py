import hashlib, hmac, json, logging, base64
from fastapi import APIRouter, Request, HTTPException, Cookie, Depends
from app.core.limiter import limiter
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.database import get_db
from app.models.usuarios import Usuario

logger = logging.getLogger("floreria")
router = APIRouter()

# Legacy token for backward compat (old single-password sessions)
LEGACY_TOKEN = hashlib.sha256(
    f"{settings.PANEL_PASSWORD}:{settings.SESSION_SECRET}".encode()
).hexdigest()


def _hmac_sig(payload_str: str) -> str:
    """HMAC-SHA256 signature (full 64 hex chars)."""
    return hmac.new(settings.SESSION_SECRET.encode(), payload_str.encode(), "sha256").hexdigest()


def _make_token(user_id: int, username: str, rol: str) -> str:
    """Create session token encoding user info."""
    payload = json.dumps({"id": user_id, "u": username, "r": rol})
    sig = _hmac_sig(payload)
    return base64.b64encode(f"{payload}|{sig}".encode()).decode()


def _parse_token(token: str) -> dict | None:
    """Parse session token, return {id, u, r} or None."""
    if not token:
        return None
    # Legacy single-password token
    if token == LEGACY_TOKEN:
        return {"id": 0, "u": "admin", "r": "admin"}
    try:
        decoded = base64.b64decode(token).decode()
        payload_str, sig = decoded.rsplit("|", 1)
        expected_sig = _hmac_sig(payload_str)
        # Accept both new full HMAC and old truncated sha256 (transition)
        old_sig = hashlib.sha256(f"{payload_str}:{settings.SESSION_SECRET}".encode()).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig) and sig != old_sig:
            return None
        return json.loads(payload_str)
    except Exception:
        return None


def verificar_sesion(session_token: str | None) -> bool:
    """Backward-compatible session check — any valid token."""
    return _parse_token(session_token) is not None


def obtener_rol(session_token: str | None) -> str | None:
    """Get user role from session token."""
    info = _parse_token(session_token)
    return info["r"] if info else None


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    client_ip = request.client.host if request.client else "unknown"

    # Try username+password login
    if username:
        result = await db.execute(select(Usuario).where(Usuario.username == username, Usuario.activo == True))
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"[AUTH] Login fallido (usuario no existe): username={username} ip={client_ip}")
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        if user.password_hash != pw_hash:
            logger.warning(f"[AUTH] Login fallido (password incorrecto): username={username} ip={client_ip}")
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        token = _make_token(user.id, user.username, user.rol)
        redirect = {
            "admin": "/panel/",
            "operador": "/panel/pos",
            "florista": "/panel/taller",
            "repartidor": "/panel/repartidor",
        }.get(user.rol, "/panel/")
        logger.info(f"[AUTH] Login exitoso: username={username} rol={user.rol} ip={client_ip}")
        response = JSONResponse({"status": "ok", "rol": user.rol, "nombre": user.nombre, "redirect": redirect})
    else:
        # Legacy: password-only login (backward compat)
        if password != settings.PANEL_PASSWORD:
            logger.warning(f"[AUTH] Login legacy fallido ip={client_ip}")
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        token = LEGACY_TOKEN
        logger.info(f"[AUTH] Login legacy exitoso ip={client_ip}")
        response = JSONResponse({"status": "ok", "rol": "admin", "nombre": "Admin", "redirect": "/panel/"})

    response.set_cookie(
        key="panel_session",
        value=token,
        max_age=settings.SESION_DURACION,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT == "production",
        path="/",
    )
    return response


@router.get("/logout")
async def logout():
    response = HTMLResponse('<script>location.href="/panel/"</script>')
    response.delete_cookie("panel_session", path="/")
    return response


@router.get("/me")
async def me(panel_session: str | None = Cookie(default=None)):
    """Return current user info from session."""
    info = _parse_token(panel_session)
    if not info:
        raise HTTPException(status_code=401, detail="No autenticado")
    return {"username": info["u"], "rol": info["r"]}
