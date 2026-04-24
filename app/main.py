from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
from app.database import inicializar_db
from app.core.config import settings
from app.routers import pedidos, productos, clientes, flores, funerarias, pagos, panel, auth, catalogo, inventario, repartidor, pos, configuracion, admin, taller, reservas, claudia_proxy, pages
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("floreria")

async def _auto_liberar_chats_viejos():
    """Libera chats 'esperando_humano' con 5+ días sin actividad."""
    import asyncio, httpx, os
    from datetime import datetime, timedelta
    url = os.getenv("AGENTKIT_URL", "https://whatsapp-agentkit-production-4e69.up.railway.app")
    api_key = os.getenv("AGENTKIT_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Admin-Key"] = api_key
    while True:
        await asyncio.sleep(6 * 3600)  # cada 6 horas
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{url}/chats-activos", headers=headers)
                if r.status_code != 200:
                    continue
                chats = r.json()
                ahora = datetime.utcnow()
                for c in chats:
                    if c.get("estado") != "esperando_humano":
                        continue
                    ts = c.get("timestamp")
                    if not ts:
                        continue
                    try:
                        chat_time = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        continue
                    if (ahora - chat_time).days >= 5:
                        await client.post(f"{url}/liberar-chat", json={"telefono": c["telefono"]}, headers=headers)
                        logger.info(f"[AUTO] Chat liberado (5+ días): {c['telefono']}")
        except Exception as e:
            logger.error(f"[AUTO] Error liberando chats: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Ambiente: {settings.ENVIRONMENT}")
    task = asyncio.create_task(_auto_liberar_chats_viejos())
    yield
    task.cancel()

app = FastAPI(
    title="Florería Lucy — Ecosistema",
    version="1.0.0",
    lifespan=lifespan
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global exception handler — never leak internals to the client
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"[UNHANDLED] {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.florerialucy.com", "https://florerialucy.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bloquear acceso directo a Railway + Security Headers
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if settings.ENVIRONMENT == "production":
        host = request.headers.get("host", "")
        path = request.url.path
        # Bloquear acceso directo a railway.app, EXCEPTO:
        # - Webhooks de servicios externos (MP, etc.) que necesitan URL pública estable
        #   y no pueden usar florerialucy.com porque su DNS está proxied por Canva.
        webhook_paths = ("/pagos/mp/webhook",)
        if "railway.app" in host and not path.startswith(webhook_paths):
            return JSONResponse(status_code=403, content={"detail": "Acceso no permitido"})
    response = await call_next(request)
    # 1. Clickjacking — no permitir iframe en sitios ajenos
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # 2. CSP — controla qué recursos puede cargar el navegador
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://maps.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
        "img-src 'self' https: data: blob:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://maps.googleapis.com; "
        "child-src 'self' blob:; "
        "frame-src 'self' https://www.google.com; "
        "object-src 'none'; "
        "frame-ancestors 'self'"
    )
    # 3. No adivinar tipo de archivo — previene archivos disfrazados
    response.headers["X-Content-Type-Options"] = "nosniff"
    # 4. Forzar HTTPS siempre (1 año)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # 5. Controlar info que se envía al navegar a otro sitio
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # 6. Desactivar cámara, micrófono, ubicación
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(clientes.router, prefix="/clientes", tags=["clientes"])
app.include_router(productos.router, prefix="/productos", tags=["productos"])
app.include_router(flores.router, prefix="/flores", tags=["flores"])
app.include_router(funerarias.router, prefix="/funerarias", tags=["funerarias"])
app.include_router(pagos.router, prefix="/pagos", tags=["pagos"])
app.include_router(pedidos.router, prefix="/pedidos", tags=["pedidos"])
app.include_router(panel.router, prefix="/panel", tags=["panel"])
app.include_router(catalogo.router, prefix="/catalogo", tags=["catalogo"])
app.include_router(inventario.router, prefix="/inventario", tags=["inventario"])
app.include_router(repartidor.router, prefix="/repartidor", tags=["repartidor"])
app.include_router(pos.router, prefix="/pos", tags=["pos"])
app.include_router(configuracion.router, prefix="/configuracion", tags=["configuracion"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(taller.router, prefix="/api/taller", tags=["taller"])
app.include_router(reservas.router, prefix="/api/reservas", tags=["reservas"])
app.include_router(claudia_proxy.router, prefix="/api/claudia", tags=["claudia"])

app.include_router(pages.router, tags=["pages"])

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def landing():
    try:
        with open("app/landing.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/catalogo/")
