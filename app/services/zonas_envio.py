"""
Asignación unificada de zona de reparto + tarifa de envío por coordenadas.
Un solo GeoJSON con polígonos que tienen nombre de ruta y tarifa base.
Los overrides (tarifa actual, activa/inactiva) se leen de la tabla zonas_envio_override.
"""
import json
import os
from shapely.geometry import shape, Point
import logging

logger = logging.getLogger("floreria")

_GEOJSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "zonas_unificadas.geojson",
)

# Lista base cargada del GeoJSON al iniciar
_ZONAS_BASE: list[tuple[str, int, object]] = []  # [(nombre, tarifa_pesos, polygon)]

with open(_GEOJSON_PATH, "r", encoding="utf-8") as _f:
    _data = json.load(_f)
    for _feat in _data["features"]:
        _nombre = _feat["properties"]["nombre"]
        _tarifa = _feat["properties"]["tarifa"]
        _poly = shape(_feat["geometry"])
        _ZONAS_BASE.append((_nombre, _tarifa, _poly))

# Compatibilidad hacia atrás (algunos endpoints todavía leen _ZONAS)
_ZONAS = _ZONAS_BASE

logger.info(f"[ZONAS] Cargados {len(_ZONAS_BASE)} polígonos: {[z[0] for z in _ZONAS_BASE]}")


# ── Cache simple de overrides (5 min) ──
_OVERRIDES_CACHE: dict | None = None
_CACHE_TS: float = 0.0
_CACHE_TTL = 300  # 5 minutos


async def _cargar_overrides(db) -> dict:
    """Devuelve {nombre: {tarifa_centavos, activa}}. Usa cache."""
    import time
    global _OVERRIDES_CACHE, _CACHE_TS
    if _OVERRIDES_CACHE is not None and (time.time() - _CACHE_TS) < _CACHE_TTL:
        return _OVERRIDES_CACHE
    from sqlalchemy import text
    try:
        r = await db.execute(text("SELECT nombre, tarifa_centavos, activa FROM zonas_envio_override"))
        result = {row[0]: {"tarifa_centavos": row[1], "activa": row[2]} for row in r.fetchall()}
    except Exception as e:
        logger.warning(f"[ZONAS] Error cargando overrides: {e}")
        result = {}
    _OVERRIDES_CACHE = result
    _CACHE_TS = time.time()
    return result


def invalidar_cache_overrides():
    """Llamar cuando se actualiza alguna zona desde admin."""
    global _OVERRIDES_CACHE
    _OVERRIDES_CACHE = None


async def listar_zonas_efectivas(db) -> list[dict]:
    """Lista de zonas con tarifa efectiva (override o base) y estado activo.
    Devuelve en orden del GeoJSON. Solo para frontend (POS dropdown, admin)."""
    overrides = await _cargar_overrides(db)
    out = []
    for nombre, tarifa_pesos, _poly in _ZONAS_BASE:
        ov = overrides.get(nombre, {})
        tarifa_centavos = ov.get("tarifa_centavos") if ov.get("tarifa_centavos") is not None else tarifa_pesos * 100
        activa = ov.get("activa", True)
        out.append({
            "nombre": nombre,
            "tarifa_centavos": tarifa_centavos,
            "tarifa_pesos": tarifa_centavos // 100,
            "activa": activa,
            "tarifa_base_pesos": tarifa_pesos,
        })
    return out


async def obtener_zona_envio_db(db, lat: float, lng: float) -> dict | None:
    """Versión async que respeta overrides. Devuelve {zona, tarifa} en pesos.
    Si zona está inactiva, retorna None (fuera de cobertura)."""
    overrides = await _cargar_overrides(db)
    punto = Point(lng, lat)
    for nombre, tarifa_pesos, poligono in _ZONAS_BASE:
        if poligono.contains(punto):
            ov = overrides.get(nombre, {})
            if ov.get("activa") is False:
                logger.info(f"[ZONAS] Point({lng}, {lat}) -> {nombre} INACTIVA")
                return None
            tarifa_efectiva = ov.get("tarifa_centavos")
            if tarifa_efectiva is not None:
                tarifa_pesos_efectiva = tarifa_efectiva // 100
            else:
                tarifa_pesos_efectiva = tarifa_pesos
            logger.info(f"[ZONAS] Point({lng}, {lat}) -> {nombre} ${tarifa_pesos_efectiva}")
            return {"zona": nombre, "tarifa": tarifa_pesos_efectiva}
    logger.info(f"[ZONAS] Point({lng}, {lat}) -> FUERA DE COBERTURA")
    return None


def obtener_zona_envio(lat: float, lng: float) -> dict | None:
    """[LEGACY] Versión síncrona sin overrides. Mantener para compatibilidad.
    Las nuevas llamadas deberían usar obtener_zona_envio_db()."""
    punto = Point(lng, lat)
    for nombre, tarifa, poligono in _ZONAS_BASE:
        if poligono.contains(punto):
            logger.info(f"[ZONAS] Point({lng}, {lat}) -> {nombre} ${tarifa} (legacy sync)")
            return {"zona": nombre, "tarifa": tarifa}
    logger.info(f"[ZONAS] Point({lng}, {lat}) -> FUERA DE COBERTURA")
    return None
