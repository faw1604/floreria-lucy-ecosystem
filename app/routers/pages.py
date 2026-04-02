from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/historia", response_class=HTMLResponse)
async def historia_html():
    try:
        with open("app/pages/historia.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")


@router.get("/contacto", response_class=HTMLResponse)
async def contacto_html():
    try:
        with open("app/pages/contacto.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")


@router.get("/facturacion", response_class=HTMLResponse)
async def facturacion_html():
    try:
        with open("app/pages/facturacion.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")


@router.get("/legal", response_class=HTMLResponse)
async def legal_html():
    try:
        with open("app/pages/legal.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página no encontrada")
