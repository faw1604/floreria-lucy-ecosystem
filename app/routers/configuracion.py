import os
from fastapi import APIRouter, Depends, HTTPException, Cookie, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.configuracion import ConfiguracionNegocio
from app.routers.auth import verificar_sesion

router = APIRouter()

CLAUDIA_API_KEY = os.getenv("CLAUDIA_API_KEY", "")


async def obtener_config_dict(db: AsyncSession) -> dict:
    """Retorna todas las configs como dict {clave: valor}."""
    result = await db.execute(select(ConfiguracionNegocio))
    return {c.clave: c.valor for c in result.scalars().all()}


@router.get("/datos-pago")
async def datos_pago_para_claudia(
    x_claudia_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint para que Claudia obtenga datos de pago activos."""
    if not CLAUDIA_API_KEY or x_claudia_key != CLAUDIA_API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")

    cfg = await obtener_config_dict(db)

    # Cuentas de transferencia activas
    from app.models.cuentas import CuentaTransferencia
    ctas_result = await db.execute(
        select(CuentaTransferencia).where(CuentaTransferencia.activa == True)
    )
    cuentas = ctas_result.scalars().all()
    transferencias = [
        {"banco": c.banco, "titular": c.titular, "tarjeta": c.tarjeta, "clabe": c.clabe}
        for c in cuentas
    ]

    # OXXO
    oxxo = None
    if cfg.get("oxxo_activo") == "true":
        oxxo = {
            "nombre": cfg.get("oxxo_nombre", ""),
            "tarjeta": cfg.get("oxxo_tarjeta", ""),
        }

    # Instrucciones
    instrucciones_normal = cfg.get("mensaje_pago_normal", "")
    instrucciones_funeral = cfg.get("mensaje_pago_funeral", "")

    return {
        "transferencias": transferencias,
        "oxxo": oxxo,
        "instrucciones_normal": instrucciones_normal,
        "instrucciones_funeral": instrucciones_funeral,
    }


@router.get("/claudia-config")
async def config_para_claudia(
    x_claudia_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint para que Claudia lea su config del ecosistema."""
    if not CLAUDIA_API_KEY or x_claudia_key != CLAUDIA_API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")
    cfg = await obtener_config_dict(db)
    temporada_modo = cfg.get("temporada_modo", "regular")
    return {
        "claudia_activa": cfg.get("claudia_activa", "true") == "true",
        "abierto": cfg.get("claudia_abierto", "true") == "true",
        "temporada_alta": temporada_modo == "alta",
        "temporada_fecha_fuerte": cfg.get("temporada_fecha_fuerte", ""),
        "temporada_dias_restriccion": cfg.get("temporada_dias_restriccion", "2"),
        "mensaje_bienvenida": cfg.get("claudia_mensaje_bienvenida", "").strip(),
    }


@router.get("/")
async def listar_configuracion(
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(select(ConfiguracionNegocio).order_by(ConfiguracionNegocio.clave))
    configs = result.scalars().all()
    return [
        {"id": c.id, "clave": c.clave, "valor": c.valor, "descripcion": c.descripcion}
        for c in configs
    ]


@router.put("/{clave}")
async def actualizar_configuracion(
    clave: str,
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(ConfiguracionNegocio).where(ConfiguracionNegocio.clave == clave)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    config.valor = request.get("valor", config.valor)
    if "descripcion" in request:
        config.descripcion = request["descripcion"]
    await db.commit()
    return {"ok": True, "clave": config.clave, "valor": config.valor}


@router.post("/")
async def crear_configuracion(
    request: dict,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    config = ConfiguracionNegocio(
        clave=request["clave"],
        valor=request.get("valor", ""),
        descripcion=request.get("descripcion"),
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return {"ok": True, "id": config.id, "clave": config.clave}


@router.delete("/{clave}")
async def eliminar_configuracion(
    clave: str,
    panel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verificar_sesion(panel_session):
        raise HTTPException(status_code=401, detail="No autenticado")
    result = await db.execute(
        select(ConfiguracionNegocio).where(ConfiguracionNegocio.clave == clave)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    await db.delete(config)
    await db.commit()
    return {"ok": True}
