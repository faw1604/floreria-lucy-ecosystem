from fastapi import APIRouter, Depends, HTTPException, Cookie, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.productos import Producto
from app.routers.auth import verificar_sesion

router = APIRouter()

@router.get("/")
async def listar_productos(
    categoria: str | None = None,
    solo_disponibles: bool = False,
    activo: str | None = None,
    visible_catalogo: str | None = None,
    stock_filter: str | None = None,
    buscar: str | None = None,
    offset: int = 0,
    limit: int = 0,
    db: AsyncSession = Depends(get_db)
):
    query = select(Producto)
    if activo == "false":
        query = query.where(Producto.activo == False)
    elif activo == "true":
        query = query.where(Producto.activo == True)
    elif activo == "todos":
        pass  # no filter
    # Backward compat: old callers (POS, catálogo) send no param → only active
    elif activo in ("0",):
        query = query.where(Producto.activo == False)
    elif activo in ("1",):
        query = query.where(Producto.activo == True)
    elif activo == "all":
        pass
    else:
        query = query.where(Producto.activo == True)
    if visible_catalogo == "true":
        query = query.where(Producto.visible_catalogo == True)
    elif visible_catalogo == "false":
        query = query.where(Producto.visible_catalogo == False)
    if stock_filter == "con":
        query = query.where(Producto.stock_activo == True, Producto.stock > 0)
    elif stock_filter == "sin":
        query = query.where(Producto.stock_activo == True, Producto.stock <= 0)
    if categoria:
        query = query.where(Producto.categoria == categoria)
    if buscar:
        buscar_like = f"%{buscar}%"
        query = query.where(
            Producto.nombre.ilike(buscar_like) | Producto.codigo.ilike(buscar_like)
        )
    if solo_disponibles:
        query = query.where(Producto.disponible_hoy == True)
    query = query.order_by(Producto.categoria, Producto.nombre)
    if offset > 0:
        query = query.offset(offset)
    if limit > 0:
        query = query.limit(limit)
    result = await db.execute(query)
    productos = result.scalars().all()
    return [{"id": p.id, "codigo": p.codigo, "nombre": p.nombre, "categoria": p.categoria, "precio": p.precio, "precio_descuento": p.precio_descuento, "disponible_hoy": p.disponible_hoy, "imagen_url": p.imagen_url, "etiquetas": p.etiquetas, "dimensiones": p.dimensiones, "activo": p.activo, "visible_catalogo": p.visible_catalogo, "stock_activo": p.stock_activo, "stock": p.stock, "medida_alto": float(p.medida_alto) if p.medida_alto else None, "medida_ancho": float(p.medida_ancho) if p.medida_ancho else None, "costo_unitario": float(p.costo_unitario) if p.costo_unitario else None, "destacado": p.destacado} for p in productos]

@router.get("/{producto_id}")
async def obtener_producto(producto_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Producto).where(Producto.id == producto_id))
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"id": producto.id, "codigo": producto.codigo, "nombre": producto.nombre, "categoria": producto.categoria, "precio": producto.precio, "precio_descuento": producto.precio_descuento, "costo": producto.costo, "disponible_hoy": producto.disponible_hoy, "descripcion": producto.descripcion, "imagen_url": producto.imagen_url, "etiquetas": producto.etiquetas, "dimensiones": producto.dimensiones, "activo": producto.activo, "visible_catalogo": producto.visible_catalogo, "stock_activo": producto.stock_activo, "stock": producto.stock, "medida_alto": float(producto.medida_alto) if producto.medida_alto else None, "medida_ancho": float(producto.medida_ancho) if producto.medida_ancho else None, "destacado": producto.destacado}

@router.post("/")
async def crear_producto(
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    producto = Producto(
        codigo=request.get("codigo"),
        nombre=request.get("nombre", ""),
        categoria=request.get("categoria", ""),
        precio=request.get("precio", 0),
        precio_descuento=request.get("precio_descuento"),
        costo=request.get("costo", 0),
        costo_unitario=request.get("costo_unitario"),
        activo=request.get("activo", True),
        disponible_hoy=request.get("disponible_hoy", True),
        visible_catalogo=request.get("visible_catalogo", True),
        descripcion=request.get("descripcion"),
        imagen_url=request.get("imagen_url"),
        stock_activo=request.get("stock_activo", False),
        stock=request.get("stock", 0),
        medida_alto=request.get("medida_alto"),
        medida_ancho=request.get("medida_ancho"),
        destacado=request.get("destacado", False),
        vender_por_fraccion=request.get("vender_por_fraccion", False),
    )
    db.add(producto)
    await db.commit()
    await db.refresh(producto)
    return {"id": producto.id, "nombre": producto.nombre}

@router.patch("/{producto_id}")
async def actualizar_producto(
    producto_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Producto).where(Producto.id == producto_id))
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for campo in ["nombre", "categoria", "precio", "precio_descuento", "costo", "activo", "disponible_hoy", "descripcion", "etiquetas", "dimensiones", "imagen_url", "visible_catalogo", "codigo", "stock_activo", "stock", "medida_alto", "medida_ancho", "costo_unitario", "destacado", "vender_por_fraccion"]:
        if campo in request:
            setattr(producto, campo, request[campo])
    await db.commit()
    return {"id": producto.id, "nombre": producto.nombre, "precio": producto.precio}


@router.put("/{producto_id}")
async def actualizar_producto_put(
    producto_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    return await actualizar_producto(producto_id, request, panel_session, db)


@router.post("/subir-imagen")
async def subir_imagen(
    imagen: UploadFile = File(...),
    panel_session: str | None = Cookie(default=None),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    import cloudinary, cloudinary.uploader, os
    from datetime import datetime
    from app.core.config import TZ
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "ddku2wmpk"),
        api_key=os.getenv("CLOUDINARY_API_KEY", "543563876228939"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
    )
    contents = await imagen.read()
    result = cloudinary.uploader.upload(contents, folder="productos")
    return {"url": result["secure_url"]}


@router.patch("/{producto_id}/imagen")
async def actualizar_imagen(
    producto_id: int,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Producto).where(Producto.id == producto_id))
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    producto.imagen_url = request.get("imagen_url")
    await db.commit()
    return {"id": producto.id, "nombre": producto.nombre, "imagen_url": producto.imagen_url}

@router.delete("/{producto_id}")
async def desactivar_producto(
    producto_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(Producto).where(Producto.id == producto_id))
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    producto.activo = False
    await db.commit()
    return {"status": "ok", "mensaje": f"Producto {producto.nombre} desactivado"}
