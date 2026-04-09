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

@asynccontextmanager
async def lifespan(app: FastAPI):
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Ambiente: {settings.ENVIRONMENT}")
    yield

app = FastAPI(
    title="Florería Lucy — Ecosistema",
    version="1.0.0",
    lifespan=lifespan
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
        # Bloquear acceso directo a railway.app
        if "railway.app" in host:
            return JSONResponse(status_code=403, content={"detail": "Acceso no permitido"})
    response = await call_next(request)
    # 1. Clickjacking — no permitir iframe en sitios ajenos
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # 2. CSP — controla qué recursos puede cargar el navegador
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://maps.googleapis.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' https: data:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://maps.googleapis.com; "
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
