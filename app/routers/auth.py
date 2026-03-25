import hashlib
from fastapi import APIRouter, Request, HTTPException, Cookie
from fastapi.responses import JSONResponse
from app.core.config import settings

router = APIRouter()

SESSION_TOKEN_VALID = hashlib.sha256(
    f"{settings.PANEL_PASSWORD}:{settings.SESSION_SECRET}".encode()
).hexdigest()

def verificar_sesion(session_token: str | None) -> bool:
    if not session_token:
        return False
    return session_token == SESSION_TOKEN_VALID

@router.post("/login")
async def login(request: Request):
    data = await request.json()
    password = data.get("password", "")
    if password != settings.PANEL_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        key="panel_session",
        value=SESSION_TOKEN_VALID,
        max_age=settings.SESION_DURACION,
        httponly=True,
        samesite="lax",
    )
    return response

@router.get("/logout")
async def logout():
    from fastapi.responses import HTMLResponse
    response = HTMLResponse('<script>location.href="/panel"</script>')
    response.delete_cookie("panel_session")
    return response
