"""
Asignación unificada de zona de reparto + tarifa de envío por coordenadas.
Un solo GeoJSON con polígonos que tienen nombre de ruta y tarifa.
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

_ZONAS: list[tuple[str, int, object]] = []  # [(nombre, tarifa, polygon)]

with open(_GEOJSON_PATH, "r", encoding="utf-8") as _f:
    _data = json.load(_f)
    for _feat in _data["features"]:
        _nombre = _feat["properties"]["nombre"]
        _tarifa = _feat["properties"]["tarifa"]
        _poly = shape(_feat["geometry"])
        _ZONAS.append((_nombre, _tarifa, _poly))

logger.info(f"[ZONAS] Cargados {len(_ZONAS)} polígonos unificados: {[z[0] for z in _ZONAS]}")


def obtener_zona_envio(lat: float, lng: float) -> dict | None:
    """Retorna {"zona": "PONIENTE 1", "tarifa": 99} o None si fuera de cobertura."""
    punto = Point(lng, lat)
    for nombre, tarifa, poligono in _ZONAS:
        if poligono.contains(punto):
            logger.info(f"[ZONAS] Point({lng}, {lat}) -> {nombre} ${tarifa} (contains)")
            return {"zona": nombre, "tarifa": tarifa}
    # Fuera de cobertura
    logger.info(f"[ZONAS] Point({lng}, {lat}) -> FUERA DE COBERTURA")
    return None
