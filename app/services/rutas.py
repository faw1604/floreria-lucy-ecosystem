"""
Asignación automática de ruta por coordenadas.
Carga el GeoJSON una sola vez al importar y usa shapely para point-in-polygon.
"""
import json
import os
import logging
from shapely.geometry import shape, Point

logger = logging.getLogger("floreria")

_GEOJSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "rutas_chihuahua.geojson",
)

# Cargar zonas en memoria al importar
_ZONAS: list[tuple[str, object]] = []

with open(_GEOJSON_PATH, "r", encoding="utf-8") as _f:
    _data = json.load(_f)
    for _feat in _data["features"]:
        _name = _feat["properties"]["name"]
        _poly = shape(_feat["geometry"])
        _ZONAS.append((_name, _poly))

_first_coords = _data["features"][0]["geometry"]["coordinates"][0][0] if _data["features"] else []
logger.info(f"[RUTAS] Cargados {len(_ZONAS)} poligonos: {[z[0] for z in _ZONAS]}")
logger.info(f"[RUTAS] Primer vertice del primer poligono (lng,lat): {_first_coords}")


def obtener_ruta(lat: float, lng: float) -> str | None:
    """Retorna el nombre de la zona. Fallback: zona más cercana por distancia al polígono."""
    punto = Point(lng, lat)  # shapely usa (x=lng, y=lat)

    # Primero intentar contains
    for nombre, poligono in _ZONAS:
        if poligono.contains(punto):
            logger.info(f"[RUTAS] Point({lng}, {lat}) -> {nombre} (contains)")
            return nombre

    # Fallback: zona más cercana por distancia al borde del polígono
    min_dist = float("inf")
    zona_cercana = None
    for nombre, poligono in _ZONAS:
        dist = poligono.distance(punto)
        if dist < min_dist:
            min_dist = dist
            zona_cercana = nombre
    logger.info(f"[RUTAS] Point({lng}, {lat}) -> {zona_cercana} (nearest, dist={min_dist:.6f})")
    return zona_cercana
