from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.database import inicializar_db
from app.core.config import settings
from app.routers import pedidos, productos, clientes, flores, funerarias, pagos, panel, auth, catalogo, inventario, repartidor, pos, configuracion, admin, taller, reservas, claudia_proxy
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def landing():
    try:
        with open("app/landing.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/catalogo/")
