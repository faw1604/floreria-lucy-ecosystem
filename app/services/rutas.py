"""
Asignación automática de ruta por coordenadas.
Carga el GeoJSON una sola vez al importar y usa shapely para point-in-polygon.
"""
import json
import os
from shapely.geometry import shape, Point

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


def obtener_ruta(lat: float, lng: float) -> str | None:
    """Retorna el nombre de la zona en la que cae el punto, o None."""
    punto = Point(lng, lat)  # shapely usa (x=lng, y=lat)
    for nombre, poligono in _ZONAS:
        if poligono.contains(punto):
            return nombre
    return None
