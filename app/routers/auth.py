import hashlib, json
from fastapi import APIRouter, Request, HTTPException, Cookie, Depends
from app.core.limiter import limiter
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.database import get_db
from app.models.usuarios import Usuario

router = APIRouter()

# Legacy token for backward compat (old single-password sessions)
LEGACY_TOKEN = hashlib.sha256(
    f"{settings.PANEL_PASSWORD}:{settings.SESSION_SECRET}".encode()
).hexdigest()


def _make_token(user_id: int, username: str, rol: str) -> str:
    """Create session token encoding user info."""
    payload = json.dumps({"id": user_id, "u": username, "r": rol})
    sig = hashlib.sha256(f"{payload}:{settings.SESSION_SECRET}".encode()).hexdigest()[:16]
    import base64
    return base64.b64encode(f"{payload}|{sig}".encode()).decode()


def _parse_token(token: str) -> dict | None:
    """Parse session token, return {id, u, r} or None."""
    if not token:
        return None
    # Legacy single-password token
    if token == LEGACY_TOKEN:
        return {"id": 0, "u": "admin", "r": "admin"}
    try:
        import base64
        decoded = base64.b64decode(token).decode()
        payload_str, sig = decoded.rsplit("|", 1)
        expected_sig = hashlib.sha256(f"{payload_str}:{settings.SESSION_SECRET}".encode()).hexdigest()[:16]
        if sig != expected_sig:
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

    # Try username+password login
    if username:
        result = await db.execute(select(Usuario).where(Usuario.username == username, Usuario.activo == True))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        if user.password_hash != pw_hash:
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        token = _make_token(user.id, user.username, user.rol)
        redirect = {
            "admin": "/panel/",
            "operador": "/panel/pos",
            "florista": "/panel/taller",
            "repartidor": "/panel/repartidor",
        }.get(user.rol, "/panel/")
        response = JSONResponse({"status": "ok", "rol": user.rol, "nombre": user.nombre, "redirect": redirect})
    else:
        # Legacy: password-only login (backward compat)
        if password != settings.PANEL_PASSWORD:
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        token = LEGACY_TOKEN
        response = JSONResponse({"status": "ok", "rol": "admin", "nombre": "Admin", "redirect": "/panel/"})

    response.set_cookie(
        key="panel_session",
        value=token,
        max_age=settings.SESION_DURACION,
        httponly=True,
        samesite="lax",
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
