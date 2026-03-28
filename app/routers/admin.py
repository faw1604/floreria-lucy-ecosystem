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
from app.models.egresos import Egreso, GastoRecurrente, MetodoPagoEgreso, OtroIngreso
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
    desde: str | None = None, hasta: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    sql = "SELECT id, fecha, concepto, categoria, monto, metodo_pago, notas, referencia, es_recurrente FROM egresos"
    params = {}
    wheres = []
    if desde:
        wheres.append("fecha >= :desde")
        params["desde"] = date.fromisoformat(desde)
    if hasta:
        wheres.append("fecha <= :hasta")
        params["hasta"] = date.fromisoformat(hasta)
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    sql += " ORDER BY fecha DESC LIMIT 500"
    result = await db.execute(text(sql), params)
    return [
        {"id": r[0], "fecha": str(r[1]), "concepto": r[2], "categoria": r[3],
         "monto": r[4], "metodo_pago": r[5], "notas": r[6], "referencia": r[7],
         "es_recurrente": r[8]}
        for r in result.fetchall()
    ]


@router.post("/egresos")
async def crear_egreso(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    try:
        fecha_val = date.fromisoformat(data["fecha"]) if isinstance(data["fecha"], str) else data["fecha"]
        await db.execute(text("""
            INSERT INTO egresos (fecha, concepto, categoria, monto, metodo_pago, notas, referencia, es_recurrente)
            VALUES (:f, :c, :cat, :m, :mp, :n, :ref, :er)
        """), {
            "f": fecha_val, "c": data["concepto"], "cat": data.get("categoria", "otro"),
            "m": data.get("monto", 0), "mp": data.get("metodo_pago"),
            "n": data.get("notas"), "ref": data.get("referencia"),
            "er": data.get("es_recurrente", False),
        })
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/egresos/{egreso_id}")
async def actualizar_egreso(
    egreso_id: int,
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    sets = []
    params = {"id": egreso_id}
    for k in ["concepto", "categoria", "monto", "metodo_pago", "notas", "referencia"]:
        if k in data:
            sets.append(f"{k} = :{k}")
            params[k] = data[k]
    if "fecha" in data:
        sets.append("fecha = :fecha")
        params["fecha"] = date.fromisoformat(data["fecha"]) if isinstance(data["fecha"], str) else data["fecha"]
    if not sets:
        return {"ok": True}
    await db.execute(text(f"UPDATE egresos SET {', '.join(sets)} WHERE id = :id"), params)
    await db.commit()
    return {"ok": True}


@router.delete("/egresos/{egreso_id}")
async def eliminar_egreso(
    egreso_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    await db.execute(text("DELETE FROM egresos WHERE id = :id"), {"id": egreso_id})
    await db.commit()
    return {"ok": True}


# --- Gastos recurrentes ---

@router.get("/gastos-recurrentes")
async def listar_gastos_recurrentes(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(GastoRecurrente).order_by(GastoRecurrente.nombre))
    return [
        {"id": g.id, "nombre": g.nombre, "categoria": g.categoria,
         "frecuencia": g.frecuencia, "monto_sugerido": g.monto_sugerido, "activo": g.activo}
        for g in result.scalars().all()
    ]


@router.post("/gastos-recurrentes")
async def crear_gasto_recurrente(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    g = GastoRecurrente(
        nombre=data["nombre"], categoria=data.get("categoria", "otro"),
        frecuencia=data.get("frecuencia", "mensual"),
        monto_sugerido=data.get("monto_sugerido", 0), activo=True,
    )
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return {"ok": True, "id": g.id}


@router.put("/gastos-recurrentes/{gasto_id}")
async def actualizar_gasto_recurrente(
    gasto_id: int, request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(GastoRecurrente).where(GastoRecurrente.id == gasto_id))
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="No encontrado")
    data = await request.json()
    for k in ["nombre", "categoria", "frecuencia", "monto_sugerido", "activo"]:
        if k in data:
            setattr(g, k, data[k])
    await db.commit()
    return {"ok": True}


@router.delete("/gastos-recurrentes/{gasto_id}")
async def eliminar_gasto_recurrente(
    gasto_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(GastoRecurrente).where(GastoRecurrente.id == gasto_id))
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="No encontrado")
    await db.delete(g)
    await db.commit()
    return {"ok": True}


# --- Métodos de pago egresos ---

@router.get("/metodos-pago-egreso")
async def listar_metodos_pago_egreso(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(MetodoPagoEgreso).order_by(MetodoPagoEgreso.nombre))
    return [{"id": m.id, "nombre": m.nombre, "activo": m.activo} for m in result.scalars().all()]


@router.post("/metodos-pago-egreso")
async def crear_metodo_pago_egreso(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    m = MetodoPagoEgreso(nombre=data["nombre"], activo=True)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return {"ok": True, "id": m.id}


@router.put("/metodos-pago-egreso/{mp_id}")
async def actualizar_metodo_pago_egreso(
    mp_id: int, request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(MetodoPagoEgreso).where(MetodoPagoEgreso.id == mp_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="No encontrado")
    data = await request.json()
    if "nombre" in data: m.nombre = data["nombre"]
    if "activo" in data: m.activo = data["activo"]
    await db.commit()
    return {"ok": True}


@router.delete("/metodos-pago-egreso/{mp_id}")
async def eliminar_metodo_pago_egreso(
    mp_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(MetodoPagoEgreso).where(MetodoPagoEgreso.id == mp_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="No encontrado")
    # Check if has associated egresos
    count = await db.execute(select(func.count(Egreso.id)).where(Egreso.metodo_pago == m.nombre))
    if (count.scalar() or 0) > 0:
        raise HTTPException(status_code=400, detail="Tiene egresos registrados — desactívalo en vez de eliminar")
    await db.delete(m)
    await db.commit()
    return {"ok": True}


# --- Exportar egresos Excel ---

@router.get("/egresos/exportar")
async def exportar_egresos(
    desde: str | None = None, hasta: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    from fastapi.responses import StreamingResponse
    import io, openpyxl
    query = select(Egreso).order_by(Egreso.fecha.desc())
    if desde: query = query.where(Egreso.fecha >= desde)
    if hasta: query = query.where(Egreso.fecha <= hasta)
    result = await db.execute(query)
    egresos = result.scalars().all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Egresos"
    headers = ["Fecha", "Concepto", "Categoría", "Método de pago", "Monto", "Notas"]
    ws.append(headers)
    for c in range(1, len(headers)+1): ws.cell(row=1, column=c).font = openpyxl.styles.Font(bold=True)
    for e in egresos:
        ws.append([str(e.fecha), e.concepto, e.categoria, e.metodo_pago or "", round(e.monto/100, 2), e.notas or ""])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    hoy = datetime.now(TZ).strftime("%Y-%m-%d")
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=egresos_{hoy}.xlsx"})


# --- Otros ingresos ---

@router.get("/otros-ingresos")
async def listar_otros_ingresos(
    desde: str | None = None, hasta: str | None = None,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    query = select(OtroIngreso).order_by(OtroIngreso.fecha.desc())
    if desde: query = query.where(OtroIngreso.fecha >= desde)
    if hasta: query = query.where(OtroIngreso.fecha <= hasta)
    result = await db.execute(query)
    return [
        {"id": o.id, "fecha": str(o.fecha), "concepto": o.concepto,
         "monto": o.monto, "metodo_pago": o.metodo_pago, "notas": o.notas}
        for o in result.scalars().all()
    ]


@router.post("/otros-ingresos")
async def crear_otro_ingreso(
    request: Request,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    data = await request.json()
    o = OtroIngreso(
        fecha=data["fecha"], concepto=data["concepto"],
        monto=data.get("monto", 0), metodo_pago=data.get("metodo_pago"),
        notas=data.get("notas"),
    )
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return {"ok": True, "id": o.id}


@router.delete("/otros-ingresos/{oi_id}")
async def eliminar_otro_ingreso(
    oi_id: int,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    result = await db.execute(select(OtroIngreso).where(OtroIngreso.id == oi_id))
    o = result.scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=404, detail="No encontrado")
    await db.delete(o)
    await db.commit()
    return {"ok": True}


# --- Flujo de caja ---

@router.get("/finanzas/flujo-caja")
async def flujo_caja(
    desde: str, hasta: str,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    _auth(panel_session)
    # Ingresos por día
    ingresos = await db.execute(text("""
        SELECT fecha_entrega::date as fecha, COALESCE(SUM(total),0) as total
        FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h
          AND estado NOT IN ('Cancelado','rechazado') AND pago_confirmado = true
        GROUP BY fecha_entrega::date ORDER BY fecha
    """), _dp(desde, hasta))
    ing_map = {str(r[0]): r[1] for r in ingresos.fetchall()}
    # Otros ingresos por día
    otros = await db.execute(text("""
        SELECT fecha::date as fecha, COALESCE(SUM(monto),0) as total
        FROM otros_ingresos WHERE fecha BETWEEN :d AND :h
        GROUP BY fecha::date ORDER BY fecha
    """), _dp(desde, hasta))
    for r in otros.fetchall():
        ing_map[str(r[0])] = ing_map.get(str(r[0]), 0) + r[1]
    # Egresos por día
    egresos = await db.execute(text("""
        SELECT fecha::date as fecha, COALESCE(SUM(monto),0) as total
        FROM egresos WHERE fecha BETWEEN :d AND :h
        GROUP BY fecha::date ORDER BY fecha
    """), _dp(desde, hasta))
    egr_map = {str(r[0]): r[1] for r in egresos.fetchall()}
    # Build day-by-day
    d = date.fromisoformat(desde)
    h = date.fromisoformat(hasta)
    days = []
    acum = 0
    while d <= h:
        ds = str(d)
        ing = ing_map.get(ds, 0)
        egr = egr_map.get(ds, 0)
        saldo = ing - egr
        acum += saldo
        days.append({"fecha": ds, "ingresos": ing, "egresos": egr, "saldo": saldo, "acumulado": acum})
        d += timedelta(days=1)
    return days


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

_VENTAS_WHERE = "estado NOT IN ('Cancelado','rechazado') AND pago_confirmado = true"

def _dp(desde: str, hasta: str):
    """Parse date strings to date objects for asyncpg bind params."""
    return {"d": date.fromisoformat(desde), "h": date.fromisoformat(hasta)}

@router.get("/estadisticas/facturacion")
async def est_facturacion(desde: str, hasta: str, panel_session: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    _auth(panel_session)
    # Total ventas
    r = await db.execute(text(f"SELECT COALESCE(SUM(total),0),COUNT(*) FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}"), _dp(desde,hasta))
    total_ventas, num_ventas = r.one()
    # Otros ingresos
    r2 = await db.execute(text("SELECT COALESCE(SUM(monto),0) FROM otros_ingresos WHERE fecha BETWEEN :d AND :h"), _dp(desde,hasta))
    total_otros = r2.scalar() or 0
    total = total_ventas + total_otros
    # vs anterior
    dias = (date.fromisoformat(hasta) - date.fromisoformat(desde)).days + 1
    ant_hasta = (date.fromisoformat(desde) - timedelta(days=1)).isoformat()
    ant_desde = (date.fromisoformat(desde) - timedelta(days=dias)).isoformat()
    r3 = await db.execute(text(f"SELECT COALESCE(SUM(total),0) FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}"), _dp(ant_desde,ant_hasta))
    r3b = await db.execute(text("SELECT COALESCE(SUM(monto),0) FROM otros_ingresos WHERE fecha BETWEEN :d AND :h"), _dp(ant_desde,ant_hasta))
    total_ant = (r3.scalar() or 0) + (r3b.scalar() or 0)
    vs = round((total - total_ant) / total_ant * 100, 1) if total_ant else 0
    # Por día
    rd = await db.execute(text(f"SELECT fecha_entrega::date as f, COALESCE(SUM(total),0) as t, COUNT(*) as c FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE} GROUP BY f ORDER BY f"), _dp(desde,hasta))
    por_dia = [{"fecha":str(r[0]),"total":r[1],"ventas":r[2]} for r in rd.fetchall()]
    # Por hora
    rh = await db.execute(text(f"SELECT EXTRACT(HOUR FROM fecha_pedido) as h, COALESCE(SUM(total),0) as t, COUNT(*) as c FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE} GROUP BY h ORDER BY h"), _dp(desde,hasta))
    por_hora = [{"hora":int(r[0]),"total":r[1],"ventas":r[2]} for r in rh.fetchall()]
    return {"total":total,"total_ventas":total_ventas,"total_otros":total_otros,"num_ventas":num_ventas,"vs_anterior":vs,"por_dia":por_dia,"por_hora":por_hora}

@router.get("/estadisticas/ticket-medio")
async def est_ticket(desde: str, hasta: str, panel_session: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    _auth(panel_session)
    r = await db.execute(text(f"SELECT COALESCE(SUM(total),0),COUNT(*) FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}"), _dp(desde,hasta))
    total, count = r.one()
    valor = round(total / count) if count else 0
    # vs anterior
    dias = (date.fromisoformat(hasta) - date.fromisoformat(desde)).days + 1
    ad = (date.fromisoformat(desde) - timedelta(days=dias)).isoformat()
    ah = (date.fromisoformat(desde) - timedelta(days=1)).isoformat()
    ra = await db.execute(text(f"SELECT COALESCE(SUM(total),0),COUNT(*) FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}"), _dp(ad,ah))
    ta, ca = ra.one()
    va = round(ta/ca) if ca else 0
    vs = round((valor-va)/va*100,1) if va else 0
    rd = await db.execute(text(f"SELECT fecha_entrega::date as f, COALESCE(AVG(total),0)::int as avg, MIN(total) as mn, MAX(total) as mx FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE} GROUP BY f ORDER BY f"), _dp(desde,hasta))
    por_dia = [{"fecha":str(r[0]),"promedio":r[1],"min":r[2],"max":r[3]} for r in rd.fetchall()]
    return {"valor":valor,"vs_anterior":vs,"por_dia":por_dia}

@router.get("/estadisticas/ganancia")
async def est_ganancia(desde: str, hasta: str, panel_session: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    _auth(panel_session)
    r = await db.execute(text(f"""
        SELECT ped.fecha_entrega::date as f, ped.total as venta,
               COALESCE(SUM(ip.cantidad * COALESCE(p.costo_unitario*100, p.costo, 0)),0)::bigint as costo_total,
               COUNT(CASE WHEN p.costo_unitario IS NULL AND p.costo=0 THEN 1 END) as sin_costo
        FROM pedidos ped JOIN items_pedido ip ON ip.pedido_id=ped.id
        JOIN productos p ON p.id=ip.producto_id
        WHERE ped.fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}
        GROUP BY ped.id, ped.fecha_entrega, ped.total
    """), _dp(desde,hasta))
    rows = r.fetchall()
    total_venta = sum(r[1] for r in rows)
    total_costo = sum(r[2] for r in rows)
    total_ganancia = total_venta - total_costo
    sin_costo = sum(1 for r in rows if r[3] > 0)
    # Por día
    dia_map = {}
    for r in rows:
        d = str(r[0])
        if d not in dia_map: dia_map[d] = {"fecha":d,"facturacion":0,"costo":0,"ganancia":0}
        dia_map[d]["facturacion"] += r[1]; dia_map[d]["costo"] += r[2]
        dia_map[d]["ganancia"] = dia_map[d]["facturacion"] - dia_map[d]["costo"]
    por_dia = sorted(dia_map.values(), key=lambda x: x["fecha"])
    for d in por_dia: d["margen"] = round(d["ganancia"]/d["facturacion"]*100,1) if d["facturacion"] else 0
    return {"total":total_ganancia,"facturacion":total_venta,"costo":total_costo,"productos_sin_costo":sin_costo,"por_dia":por_dia}

@router.get("/estadisticas/medios-pago")
async def est_medios(desde: str, hasta: str, panel_session: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    _auth(panel_session)
    r = await db.execute(text(f"SELECT COALESCE(forma_pago,'Sin info') as mp, COUNT(*) as c, COALESCE(SUM(total),0) as t FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE} GROUP BY forma_pago ORDER BY t DESC"), _dp(desde,hasta))
    rows = [{"metodo":r[0],"count":r[1],"total":r[2]} for r in r.fetchall()]
    grand = sum(r["total"] for r in rows) or 1
    for r in rows: r["porcentaje"] = round(r["total"]/grand*100,1)
    mas_usado = rows[0]["metodo"] if rows else "—"
    return {"mas_usado":mas_usado,"distribucion":rows}

@router.get("/estadisticas/productos-top")
async def est_productos(desde: str, hasta: str, panel_session: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    _auth(panel_session)
    r = await db.execute(text(f"""
        SELECT p.nombre, p.categoria, SUM(ip.cantidad) as qty, SUM(ip.cantidad*ip.precio_unitario) as val
        FROM items_pedido ip JOIN pedidos ped ON ped.id=ip.pedido_id JOIN productos p ON p.id=ip.producto_id
        WHERE ped.fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}
        GROUP BY p.nombre, p.categoria ORDER BY val DESC LIMIT 10
    """), _dp(desde,hasta))
    por_valor = [{"nombre":r[0],"categoria":r[1],"cantidad":int(r[2]),"total":r[3]} for r in r.fetchall()]
    r2 = await db.execute(text(f"""
        SELECT p.nombre, p.categoria, SUM(ip.cantidad) as qty, SUM(ip.cantidad*ip.precio_unitario) as val
        FROM items_pedido ip JOIN pedidos ped ON ped.id=ip.pedido_id JOIN productos p ON p.id=ip.producto_id
        WHERE ped.fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}
        GROUP BY p.nombre, p.categoria ORDER BY qty DESC LIMIT 10
    """), _dp(desde,hasta))
    por_cantidad = [{"nombre":r[0],"categoria":r[1],"cantidad":int(r[2]),"total":r[3]} for r in r2.fetchall()]
    return {"por_valor":por_valor,"por_cantidad":por_cantidad}

@router.get("/estadisticas/clientes-top")
async def est_clientes(desde: str, hasta: str, panel_session: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    _auth(panel_session)
    r = await db.execute(text(f"""
        SELECT c.nombre, COUNT(ped.id) as n, SUM(ped.total) as t, MAX(ped.fecha_entrega) as ult
        FROM pedidos ped JOIN clientes c ON c.id=ped.customer_id
        WHERE ped.fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}
        GROUP BY c.id, c.nombre ORDER BY t DESC LIMIT 10
    """), _dp(desde,hasta))
    por_valor = [{"nombre":r[0],"pedidos":r[1],"total":r[2],"ticket_medio":round(r[2]/r[1]) if r[1] else 0,"ultima":str(r[3]) if r[3] else None} for r in r.fetchall()]
    r2 = await db.execute(text(f"""
        SELECT c.nombre, COUNT(ped.id) as n, SUM(ped.total) as t, MAX(ped.fecha_entrega) as ult
        FROM pedidos ped JOIN clientes c ON c.id=ped.customer_id
        WHERE ped.fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE}
        GROUP BY c.id, c.nombre ORDER BY n DESC LIMIT 10
    """), _dp(desde,hasta))
    por_compras = [{"nombre":r[0],"pedidos":r[1],"total":r[2],"ticket_medio":round(r[2]/r[1]) if r[1] else 0,"ultima":str(r[3]) if r[3] else None} for r in r2.fetchall()]
    return {"por_valor":por_valor,"por_compras":por_compras}

@router.get("/estadisticas/canales")
async def est_canales(desde: str, hasta: str, panel_session: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    _auth(panel_session)
    r = await db.execute(text(f"SELECT canal, COUNT(*) as c, COALESCE(SUM(total),0) as t FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE} GROUP BY canal"), _dp(desde,hasta))
    rows = [{"canal":r[0],"count":r[1],"total":r[2]} for r in r.fetchall()]
    grand = sum(r["total"] for r in rows) or 1
    for r in rows: r["porcentaje"] = round(r["total"]/grand*100,1)
    rd = await db.execute(text(f"SELECT fecha_entrega::date as f, canal, COUNT(*) as c FROM pedidos WHERE fecha_entrega BETWEEN :d AND :h AND {_VENTAS_WHERE} GROUP BY f, canal ORDER BY f"), _dp(desde,hasta))
    por_dia = [{"fecha":str(r[0]),"canal":r[1],"count":r[2]} for r in rd.fetchall()]
    return {"distribucion":rows,"por_dia":por_dia}


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
               "Costo unitario", "Alto (cm)", "Ancho (cm)"]
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
            float(p.costo_unitario) if p.costo_unitario else "",
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
            costo_u = float(row[9]) if len(row) > 9 and row[9] not in (None, "") else None
            m_alto = float(row[10]) if len(row) > 10 and row[10] not in (None, "") else None
            m_ancho = float(row[11]) if len(row) > 11 and row[11] not in (None, "") else None

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
                prod.costo_unitario = costo_u
                prod.medida_alto = m_alto
                prod.medida_ancho = m_ancho
                actualizados += 1
            else:
                prod = Producto(
                    nombre=nombre, categoria=categoria, codigo=codigo,
                    descripcion=descripcion, precio=precio, precio_descuento=precio_desc,
                    visible_catalogo=visible, stock_activo=stock_activo, stock=stock_val,
                    costo_unitario=costo_u, medida_alto=m_alto, medida_ancho=m_ancho,
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
