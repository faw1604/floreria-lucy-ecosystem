"""
Asignación de ruta por coordenadas — usa el mismo GeoJSON unificado de zonas_envio.
"""
from app.services.zonas_envio import obtener_zona_envio
import logging

logger = logging.getLogger("floreria")


def obtener_ruta(lat: float, lng: float) -> str | None:
    """Retorna el nombre de la zona/ruta. Usa el GeoJSON unificado."""
    zona = obtener_zona_envio(lat, lng)
    if zona:
        return zona["zona"]
    return None
