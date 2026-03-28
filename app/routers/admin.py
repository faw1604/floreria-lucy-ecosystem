from fastapi import APIRouter, Depends, HTTPException, Cookie, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, date, timedelta
import os, cloudinary, cloudinary.uploader
from app.database import get_db
from app.core.config import TZ
from app.routers.auth import verificar_sesion
from app.models.pedidos import Pedido, ItemPedido
from app.models.productos import Producto, Categoria, ProductoVariante
import logging
logger = logging.getLogger("floreria")
from app.models.clientes import Cliente
from app.models.configuracion import CodigoDescuento
from app.models.usuarios import Usuario
from app.models.egresos import Egreso
from app.models.banners import BannerCatalogo

router = APIRouter()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "ddku2wmpk"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "543563876228939"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
)


def _auth(panel_session):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")


# ══════ USUARIOS ══════

@router.get("/usuarios")
async def listar_usuarios(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(Usuario).order_by(Usuario.created_at.desc()))
    return [
        {"id": u.id, "nombre": u.nombre, "username": u.username, "rol": u.rol,
         "activo": u.activo, "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in result.scalars().all()
    ]


@router.post("/usuarios")
async def crear_usuario(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    import hashlib
    password = data.get("password", "")
    if not password:
        raise HTTPException(status_code=400, detail="Contraseña requerida")
    # Simple hash (bcrypt si está disponible, sino SHA256)
    try:
        from passlib.hash import bcrypt
        pw_hash = bcrypt.hash(password)
    except ImportError:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
    u = Usuario(
        nombre=data["nombre"],
        username=data["username"],
        password_hash=pw_hash,
        rol=data.get("rol", "operador"),
        activo=data.get("activo", True),
    )
    db.add(u)
    try:
        await db.commit()
        await db.refresh(u)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Username ya existe")
    return {"ok": True, "id": u.id}


@router.put("/usuarios/{user_id}")
async def actualizar_usuario(
    user_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(Usuario).where(Usuario.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    data = await request.json()
    if "nombre" in data:
        u.nombre = data["nombre"]
    if "rol" in data:
        u.rol = data["rol"]
    if "activo" in data:
        # Prevent deactivating last admin
        if not data["activo"] and u.rol == "admin":
            count = await db.execute(select(func.count(Usuario.id)).where(Usuario.rol == "admin", Usuario.activo == True))
            if count.scalar() <= 1:
                raise HTTPException(status_code=400, detail="No se puede desactivar el último admin")
        u.activo = data["activo"]
    await db.commit()
    return {"ok": True}


@router.post("/usuarios/{user_id}/cambiar-password")
async def cambiar_password(
    user_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    password = data.get("password", "")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Contraseña muy corta")
    result = await db.execute(select(Usuario).where(Usuario.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    import hashlib
    try:
        from passlib.hash import bcrypt
        u.password_hash = bcrypt.hash(password)
    except ImportError:
        u.password_hash = hashlib.sha256(password.encode()).hexdigest()
    await db.commit()
    return {"ok": True}


# ══════ EGRESOS ══════

@router.get("/egresos")
async def listar_egresos(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(Egreso).order_by(Egreso.fecha.desc()).limit(200))
    return [
        {"id": e.id, "fecha": str(e.fecha), "concepto": e.concepto,
         "categoria": e.categoria, "monto": e.monto, "notas": e.notas}
        for e in result.scalars().all()
    ]


@router.post("/egresos")
async def crear_egreso(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    e = Egreso(
        fecha=data["fecha"],
        concepto=data["concepto"],
        categoria=data.get("categoria", "otro"),
        monto=data.get("monto", 0),
        notas=data.get("notas"),
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return {"ok": True, "id": e.id}


@router.delete("/egresos/{egreso_id}")
async def eliminar_egreso(
    egreso_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(Egreso).where(Egreso.id == egreso_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Egreso no encontrado")
    await db.delete(e)
    await db.commit()
    return {"ok": True}


# ══════ DESCUENTOS ══════

@router.get("/descuentos")
async def listar_descuentos(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(CodigoDescuento).order_by(CodigoDescuento.id.desc()))
    return [
        {"id": d.id, "codigo": d.codigo, "tipo": d.tipo, "valor": d.valor,
         "descripcion": d.descripcion, "activo": d.activo,
         "fecha_inicio": str(d.fecha_inicio) if d.fecha_inicio else None,
         "fecha_expiracion": str(d.fecha_expiracion) if d.fecha_expiracion else None,
         "usos_maximos": d.usos_maximos, "usos_actuales": d.usos_actuales}
        for d in result.scalars().all()
    ]


@router.post("/descuentos")
async def crear_descuento(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    d = CodigoDescuento(
        codigo=data["codigo"].strip().upper(),
        tipo=data.get("tipo", "porcentaje"),
        valor=data.get("valor", 0),
        descripcion=data.get("descripcion"),
        activo=data.get("activo", True),
        fecha_inicio=data.get("fecha_inicio"),
        fecha_expiracion=data.get("fecha_expiracion"),
        usos_maximos=data.get("usos_maximos"),
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return {"ok": True, "id": d.id}


@router.put("/descuentos/{desc_id}")
async def actualizar_descuento(
    desc_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(CodigoDescuento).where(CodigoDescuento.id == desc_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Descuento no encontrado")
    data = await request.json()
    for k in ["codigo", "tipo", "valor", "descripcion", "activo", "fecha_inicio", "fecha_expiracion", "usos_maximos"]:
        if k in data:
            setattr(d, k, data[k])
    await db.commit()
    return {"ok": True}


@router.delete("/descuentos/{desc_id}")
async def eliminar_descuento(
    desc_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(CodigoDescuento).where(CodigoDescuento.id == desc_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Descuento no encontrado")
    await db.delete(d)
    await db.commit()
    return {"ok": True}


# ══════ BANNERS ══════

@router.get("/banners")
async def listar_banners(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(BannerCatalogo).order_by(BannerCatalogo.orden))
    return [
        {"id": b.id, "imagen_url": b.imagen_url, "titulo": b.titulo,
         "subtitulo": b.subtitulo, "link": b.link, "orden": b.orden, "activo": b.activo}
        for b in result.scalars().all()
    ]


@router.post("/banners")
async def crear_banner(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    b = BannerCatalogo(
        imagen_url=data["imagen_url"],
        titulo=data.get("titulo"),
        subtitulo=data.get("subtitulo"),
        link=data.get("link"),
        orden=data.get("orden", 0),
        activo=data.get("activo", True),
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return {"ok": True, "id": b.id}


@router.delete("/banners/{banner_id}")
async def eliminar_banner(
    banner_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(BannerCatalogo).where(BannerCatalogo.id == banner_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Banner no encontrado")
    await db.delete(b)
    await db.commit()
    return {"ok": True}


# ══════ ESTADÍSTICAS ══════

@router.get("/estadisticas/ventas-por-dia")
async def ventas_por_dia(
    desde: str, hasta: str,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(text("""
        SELECT fecha_entrega::date as fecha, COALESCE(SUM(total), 0) as total
        FROM pedidos
        WHERE fecha_entrega BETWEEN :desde AND :hasta
          AND estado NOT IN ('Cancelado', 'rechazado')
          AND pago_confirmado = true
        GROUP BY fecha_entrega::date
        ORDER BY fecha
    """), {"desde": desde, "hasta": hasta})
    return [{"fecha": str(r[0]), "total": r[1]} for r in result.fetchall()]


@router.get("/estadisticas/productos-top")
async def productos_top(
    desde: str, hasta: str, limit: int = 10,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(text("""
        SELECT p.nombre, SUM(ip.cantidad) as cantidad
        FROM items_pedido ip
        JOIN pedidos ped ON ped.id = ip.pedido_id
        JOIN productos p ON p.id = ip.producto_id
        WHERE ped.fecha_entrega BETWEEN :desde AND :hasta
          AND ped.estado NOT IN ('Cancelado', 'rechazado')
        GROUP BY p.nombre
        ORDER BY cantidad DESC
        LIMIT :lim
    """), {"desde": desde, "hasta": hasta, "lim": limit})
    return [{"nombre": r[0], "cantidad": int(r[1])} for r in result.fetchall()]


@router.get("/estadisticas/canales")
async def canales(
    desde: str, hasta: str,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(text("""
        SELECT canal, COUNT(*) as total
        FROM pedidos
        WHERE fecha_entrega BETWEEN :desde AND :hasta
          AND estado NOT IN ('Cancelado', 'rechazado')
        GROUP BY canal
    """), {"desde": desde, "hasta": hasta})
    return [{"canal": r[0], "total": int(r[1])} for r in result.fetchall()]


@router.get("/estadisticas/zonas")
async def zonas(
    desde: str, hasta: str,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(text("""
        SELECT COALESCE(zona_entrega, 'Sin zona') as zona, COUNT(*) as cantidad
        FROM pedidos
        WHERE fecha_entrega BETWEEN :desde AND :hasta
          AND estado NOT IN ('Cancelado', 'rechazado')
          AND direccion_entrega IS NOT NULL
        GROUP BY zona_entrega
        ORDER BY cantidad DESC
    """), {"desde": desde, "hasta": hasta})
    return [{"zona": r[0], "cantidad": int(r[1])} for r in result.fetchall()]


# ══════ SUBIDA IMÁGENES ══════

@router.post("/productos/imagen")
async def subir_imagen_producto(
    imagen: UploadFile = File(...),
    panel_session: str | None = Cookie(default=None),
):
    _auth(panel_session)
    contents = await imagen.read()
    result = cloudinary.uploader.upload(
        contents,
        folder="productos",
        public_id=f"prod_{datetime.now(TZ).strftime('%Y%m%d%H%M%S')}",
    )
    return {"url": result["secure_url"]}


# ══════ EXPORTAR / IMPORTAR PRODUCTOS ══════

@router.get("/productos/exportar")
async def exportar_productos(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    from fastapi.responses import StreamingResponse
    import io, openpyxl

    result = await db.execute(select(Producto).order_by(Producto.categoria, Producto.nombre))
    productos = result.scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos"
    headers = ["Nombre", "Categoría", "Código", "Descripción", "Precio",
               "Precio de promoción", "Mostrar en el catálogo", "Controlar stock", "Stock actual",
               "Alto (cm)", "Ancho (cm)"]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        ws.cell(row=1, column=col).font = openpyxl.styles.Font(bold=True)

    for p in productos:
        ws.append([
            p.nombre,
            p.categoria,
            p.codigo or "",
            p.descripcion or "",
            round(p.precio / 100, 2) if p.precio else 0,
            round(p.precio_descuento / 100, 2) if p.precio_descuento else "",
            "S" if p.visible_catalogo else "N",
            "S" if p.stock_activo else "N",
            p.stock if p.stock_activo else "",
            float(p.medida_alto) if p.medida_alto else "",
            float(p.medida_ancho) if p.medida_ancho else "",
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    hoy = datetime.now(TZ).strftime("%Y-%m-%d")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=productos_floreria_lucy_{hoy}.xlsx"},
    )


@router.post("/productos/importar")
async def importar_productos(
    archivo: UploadFile = File(...),
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    import openpyxl, io

    contents = await archivo.read()
    wb = openpyxl.load_workbook(io.BytesIO(contents))
    ws = wb.active

    rows = list(ws.iter_rows(min_row=2, values_only=True))
    actualizados = 0
    creados = 0
    errores = 0

    for row in rows:
        try:
            if len(row) < 5:
                errores += 1
                continue
            nombre = str(row[0] or "").strip()
            categoria = str(row[1] or "").strip()
            codigo = str(row[2] or "").strip()
            descripcion = str(row[3] or "").strip() or None
            precio = int(round(float(row[4] or 0) * 100))
            precio_desc = int(round(float(row[5]) * 100)) if row[5] not in (None, "", "N/A") else None
            visible = str(row[6] or "S").strip().upper() == "S" if len(row) > 6 else True
            stock_activo = str(row[7] or "N").strip().upper() == "S" if len(row) > 7 else False
            stock_val = int(row[8] or 0) if len(row) > 8 and row[8] not in (None, "") else 0
            m_alto = float(row[9]) if len(row) > 9 and row[9] not in (None, "") else None
            m_ancho = float(row[10]) if len(row) > 10 and row[10] not in (None, "") else None

            if not nombre or not codigo:
                errores += 1
                continue

            # Ensure category exists
            cat_result = await db.execute(select(Categoria).where(Categoria.nombre == categoria))
            if not cat_result.scalar_one_or_none():
                db.add(Categoria(nombre=categoria, tipo="normal", orden=0))
                await db.flush()

            # Find by codigo
            result = await db.execute(select(Producto).where(Producto.codigo == codigo))
            prod = result.scalar_one_or_none()

            if prod:
                prod.nombre = nombre
                prod.categoria = categoria
                prod.descripcion = descripcion
                prod.precio = precio
                prod.precio_descuento = precio_desc
                prod.visible_catalogo = visible
                prod.stock_activo = stock_activo
                prod.stock = stock_val
                prod.medida_alto = m_alto
                prod.medida_ancho = m_ancho
                actualizados += 1
            else:
                prod = Producto(
                    nombre=nombre, categoria=categoria, codigo=codigo,
                    descripcion=descripcion, precio=precio, precio_descuento=precio_desc,
                    visible_catalogo=visible, stock_activo=stock_activo, stock=stock_val,
                    medida_alto=m_alto, medida_ancho=m_ancho,
                    activo=True, disponible_hoy=True,
                )
                db.add(prod)
                creados += 1
        except Exception:
            errores += 1

    await db.commit()
    return {"ok": True, "actualizados": actualizados, "creados": creados, "errores": errores}


# ══════ CATEGORÍAS ══════

@router.get("/categorias")
async def listar_categorias(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(Categoria).order_by(Categoria.orden, Categoria.nombre))
    cats = result.scalars().all()
    items = []
    for c in cats:
        count = await db.execute(
            select(func.count(Producto.id)).where(Producto.categoria == c.nombre, Producto.activo == True)
        )
        items.append({
            "id": c.id, "nombre": c.nombre, "tipo": c.tipo,
            "orden": c.orden, "productos_activos": count.scalar() or 0,
        })
    return items


@router.post("/categorias")
async def crear_categoria(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    c = Categoria(
        nombre=data["nombre"].strip(),
        tipo=data.get("tipo", "normal"),
        orden=data.get("orden", 0),
    )
    db.add(c)
    try:
        await db.commit()
        await db.refresh(c)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Categoría ya existe")
    return {"ok": True, "id": c.id}


@router.put("/categorias/{cat_id}")
async def actualizar_categoria(
    cat_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(Categoria).where(Categoria.id == cat_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    data = await request.json()
    old_nombre = c.nombre
    for k in ["nombre", "tipo", "orden"]:
        if k in data:
            setattr(c, k, data[k])
    # Update products if category name changed
    if "nombre" in data and data["nombre"] != old_nombre:
        await db.execute(
            text("UPDATE productos SET categoria = :new WHERE categoria = :old"),
            {"new": data["nombre"], "old": old_nombre},
        )
    await db.commit()
    return {"ok": True}


@router.delete("/categorias/{cat_id}")
async def eliminar_categoria(
    cat_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(Categoria).where(Categoria.id == cat_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    count = await db.execute(
        select(func.count(Producto.id)).where(Producto.categoria == c.nombre, Producto.activo == True)
    )
    if (count.scalar() or 0) > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar: tiene productos activos")
    await db.delete(c)
    await db.commit()
    return {"ok": True}


# ══════ VARIANTES ══════

@router.get("/variantes/{producto_id}")
async def listar_variantes(
    producto_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(
        select(ProductoVariante)
        .where(ProductoVariante.producto_id == producto_id)
        .order_by(ProductoVariante.tipo, ProductoVariante.nombre)
    )
    return [
        {"id": v.id, "producto_id": v.producto_id, "tipo": v.tipo, "nombre": v.nombre,
         "codigo": v.codigo, "imagen_url": v.imagen_url, "precio": v.precio,
         "precio_descuento": v.precio_descuento, "stock_activo": v.stock_activo,
         "stock": v.stock, "activo": v.activo}
        for v in result.scalars().all()
    ]


@router.post("/variantes/{producto_id}")
async def crear_variante(
    producto_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    v = ProductoVariante(
        producto_id=producto_id,
        tipo=data["tipo"],
        nombre=data["nombre"],
        codigo=data.get("codigo"),
        imagen_url=data.get("imagen_url"),
        precio=data.get("precio", 0),
        precio_descuento=data.get("precio_descuento"),
        stock_activo=data.get("stock_activo", False),
        stock=data.get("stock", 0),
        activo=data.get("activo", True),
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return {"ok": True, "id": v.id}


@router.put("/variantes/{variante_id}")
async def actualizar_variante(
    variante_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(ProductoVariante).where(ProductoVariante.id == variante_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Variante no encontrada")
    data = await request.json()
    for k in ["tipo", "nombre", "codigo", "imagen_url", "precio", "precio_descuento", "stock_activo", "stock", "activo"]:
        if k in data:
            setattr(v, k, data[k])
    await db.commit()
    return {"ok": True}


@router.delete("/variantes/{variante_id}")
async def eliminar_variante(
    variante_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(ProductoVariante).where(ProductoVariante.id == variante_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Variante no encontrada")
    await db.delete(v)
    await db.commit()
    return {"ok": True}


# ══════ GENERAR DESCRIPCIÓN IA ══════

@router.post("/productos/generar-descripcion")
async def generar_descripcion(
    request: Request,
    panel_session: str | None = Cookie(default=None),
):
    _auth(panel_session)
    import httpx
    data = await request.json()
    nombre = data.get("nombre", "")
    categoria = data.get("categoria", "")
    desc_base = data.get("descripcion_base", "")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="API key de Anthropic no configurada")

    if desc_base:
        system = "Mejora y expande esta descripción de producto para una florería boutique. Mantén el tono elegante. Máximo 3 oraciones. Responde solo con la descripción mejorada."
        user_msg = f"Producto: {nombre} ({categoria})\nDescripción actual: {desc_base}"
    else:
        system = "Eres el asistente de Florería Lucy, una florería boutique en Chihuahua, México. Genera una descripción de producto corta, elegante y atractiva (máximo 3 oraciones) para uso en catálogo online. Responde solo con la descripción, sin comillas ni prefijos."
        user_msg = f"Producto: {nombre}\nCategoría: {categoria}"

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 300,
                "system": system,
                "messages": [{"role": "user", "content": user_msg}],
            },
            timeout=30,
        )
        d = r.json()
        descripcion = d["content"][0]["text"] if d.get("content") else ""
        return {"descripcion": descripcion}
