"""
Asignación automática de zona de envío (Morada/Azul/Verde) por coordenadas.
Carga el GeoJSON una sola vez al importar.
"""
import json
import os
from shapely.geometry import shape, Point

_GEOJSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "zonas_envio.geojson",
)

_ZONAS: list[tuple[str, int, object]] = []  # [(nombre, tarifa, polygon)]

with open(_GEOJSON_PATH, "r", encoding="utf-8") as _f:
    _data = json.load(_f)
    for _feat in _data["features"]:
        _nombre = _feat["properties"]["nombre"]
        _tarifa = _feat["properties"]["tarifa"]
        _poly = shape(_feat["geometry"])
        _ZONAS.append((_nombre, _tarifa, _poly))


def obtener_zona_envio(lat: float, lng: float) -> dict | None:
    """Retorna {"zona": "Morada", "tarifa": 99} o None si fuera de cobertura."""
    punto = Point(lng, lat)
    for nombre, tarifa, poligono in _ZONAS:
        if poligono.contains(punto):
            return {"zona": nombre, "tarifa": tarifa}
    return None
