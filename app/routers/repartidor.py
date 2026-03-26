from fastapi import APIRouter, Depends, HTTPException, Cookie, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import os
import cloudinary
import cloudinary.uploader
from app.database import get_db
from app.models.pedidos import Pedido, ItemPedido
from app.models.productos import Producto
from app.models.clientes import Cliente
from app.core.config import TZ
from app.routers.auth import verificar_sesion

router = APIRouter()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "ddku2wmpk"),
    api_key=os.getenv("CLOUDINARY_API_KEY", ""),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
)

HORARIO_ORDER = {"mañana": 0, "manana": 0, "tarde": 1, "noche": 2}
ZONA_ORDER = {"Morada": 0, "Azul": 1, "Verde": 2}


def _sort_key(p):
    h = HORARIO_ORDER.get((p.horario_entrega or "").lower(), 9)
    z = ZONA_ORDER.get(p.zona_entrega or "", 9)
    return (h, z)


async def _pedido_items_nombres(pedido_id: int, db: AsyncSession) -> list[str]:
    result = await db.execute(select(ItemPedido).where(ItemPedido.pedido_id == pedido_id))
    items = result.scalars().all()
    nombres = []
    for item in items:
        prod = (await db.execute(select(Producto).where(Producto.id == item.producto_id))).scalar_one_or_none()
        if item.es_personalizado and item.nombre_personalizado:
            nombres.append(item.nombre_personalizado)
        elif prod:
            nombres.append(prod.nombre)
    return nombres


@router.get("/entregas-hoy")
async def entregas_hoy(
    fecha: str = "hoy",
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    from datetime import timedelta
    hoy = datetime.now(TZ).date()
    manana = hoy + timedelta(days=1)
    estados = ["Listo", "En camino", "entregado", "Entregado", "intento_fallido"]
    if fecha == "manana":
        query = select(Pedido).where(Pedido.fecha_entrega == manana, Pedido.estado.in_(estados))
    elif fecha == "todos":
        query = select(Pedido).where(Pedido.fecha_entrega.in_([hoy, manana]), Pedido.estado.in_(estados))
    else:
        query = select(Pedido).where(Pedido.fecha_entrega == hoy, Pedido.estado.in_(estados))
    result = await db.execute(query)
    pedidos = sorted(result.scalars().all(), key=_sort_key)
    out = []
    for p in pedidos:
        items = await _pedido_items_nombres(p.id, db)
        cliente_nombre = None
        cliente_telefono = None
        if p.customer_id:
            cr = await db.execute(select(Cliente).where(Cliente.id == p.customer_id))
            cli = cr.scalar_one_or_none()
            if cli:
                cliente_nombre = cli.nombre
                cliente_telefono = cli.telefono
        out.append({
            "id": p.id,
            "folio": p.numero,
            "horario_entrega": p.horario_entrega,
            "zona_envio": p.zona_entrega,
            "nombre_destinatario": p.receptor_nombre,
            "telefono_destinatario": p.receptor_telefono,
            "direccion_entrega": p.direccion_entrega,
            "dedicatoria": p.dedicatoria,
            "notas_entrega": p.notas_internas,
            "metodo_pago": p.forma_pago,
            "total": p.total,
            "items": items,
            "estado": p.estado,
            "foto_entrega_url": p.foto_entrega_url,
            "nota_no_entrega": p.nota_no_entrega,
            "cliente_nombre": cliente_nombre,
            "cliente_telefono": cliente_telefono,
            "fecha_entrega": str(p.fecha_entrega) if p.fecha_entrega else None,
            "ruta": p.ruta,
            "tipo_especial": p.tipo_especial,
        })
    return out


@router.post("/iniciar-ruta")
async def iniciar_ruta(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    ids = data.get("pedido_ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="No se enviaron pedidos")
    ahora = datetime.now(TZ)
    count = 0
    for pid in ids:
        result = await db.execute(select(Pedido).where(Pedido.id == pid))
        pedido = result.scalar_one_or_none()
        if pedido and pedido.estado == "Listo":
            pedido.estado = "En camino"
            pedido.inicio_ruta_at = ahora
            count += 1
    await db.commit()
    return {"ok": True, "actualizados": count}


@router.post("/entregar/{pedido_id}")
async def entregar(
    pedido_id: int,
    foto: UploadFile = File(...),
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    if not foto or not foto.filename:
        raise HTTPException(status_code=400, detail="La foto es obligatoria")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    ahora = datetime.now(TZ)
    ts = int(ahora.timestamp())
    folio = (pedido.numero or "").replace("-", "_")
    contenido = await foto.read()

    try:
        upload_result = cloudinary.uploader.upload(
            contenido,
            folder="entregas/",
            public_id=f"{folio}_{ts}",
            resource_type="image",
        )
        foto_url = upload_result.get("secure_url", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir foto: {str(e)}")

    pedido.estado = "Entregado"
    pedido.entregado_at = ahora
    pedido.foto_entrega_url = foto_url
    await db.commit()
    return {"ok": True, "foto_url": foto_url}


@router.post("/no-entrega/{pedido_id}")
async def no_entrega(
    pedido_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    data = await request.json()
    motivo = data.get("motivo", "")
    if not motivo:
        raise HTTPException(status_code=400, detail="El motivo es obligatorio")
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    ahora = datetime.now(TZ)
    pedido.estado = "intento_fallido"
    pedido.intento_fallido_at = ahora
    pedido.nota_no_entrega = motivo
    await db.commit()
    return {"ok": True}
