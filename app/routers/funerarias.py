from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.database import get_db
from app.models.funerarias import Funeraria
from app.routers.auth import verificar_sesion
import json

router = APIRouter()

@router.get("/")
async def listar_funerarias(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Funeraria).order_by(Funeraria.nombre))
    funerarias = result.scalars().all()
    return [{"id": f.id, "nombre": f.nombre, "direccion": f.direccion, "zona": f.zona, "costo_envio": f.costo_envio} for f in funerarias]

@router.get("/buscar")
async def buscar_funeraria(nombre: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Funeraria))
    funerarias = result.scalars().all()
    nombre_lower = nombre.lower().strip()
    for f in funerarias:
        if nombre_lower in f.nombre.lower():
            return {"id": f.id, "nombre": f.nombre, "direccion": f.direccion, "zona": f.zona, "costo_envio": f.costo_envio}
        if f.aliases:
            try:
                aliases = json.loads(f.aliases)
                if any(nombre_lower in a.lower() for a in aliases):
                    return {"id": f.id, "nombre": f.nombre, "direccion": f.direccion, "zona": f.zona, "costo_envio": f.costo_envio}
            except:
                pass
    raise HTTPException(status_code=404, detail="Funeraria no encontrada")

@router.post("/")
async def crear_funeraria(
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    aliases = request.get("aliases", [])
    funeraria = Funeraria(
        nombre=request.get("nombre", ""),
        aliases=json.dumps(aliases, ensure_ascii=False),
        direccion=request.get("direccion"),
        zona=request.get("zona", "Zona Central"),
        costo_envio=request.get("costo_envio", 9900),
    )
    db.add(funeraria)
    await db.commit()
    await db.refresh(funeraria)
    return {"id": funeraria.id, "nombre": funeraria.nombre}
