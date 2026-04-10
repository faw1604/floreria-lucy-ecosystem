"""
Zonas de envío de Florería Lucy.

Centraliza el orden de zonas (por cercanía) y la agrupación por dirección
cardinal. Usado por el panel del repartidor y por la pestaña Envíos del taller.
"""

# Orden por cercanía/dificultad de ruta. Niveles 0-4.
ZONA_ORDER: dict[str, int] = {
    "Zona Central": 0,
    "NOROESTE 1": 1, "NORESTE 1": 1, "PONIENTE 1": 1, "SUR 1": 1,
    "NORESTE 2": 2, "NOROESTE 2": 2, "PONIENTE 2": 2, "SUR 2": 2, "ORIENTE 1": 2,
    "PONIENTE 3": 3, "SUR 3": 3, "SURESTE 1": 3,
    "NORTE": 4, "ORIENTE 2": 4, "SURESTE 2": 4,
}

# Agrupación por dirección cardinal (lo que ve Fer en el dropdown).
# Cada grupo define qué sub-zonas incluye, exactamente como están en BD.
GRUPOS_ZONAS: dict[str, list[str]] = {
    "Central":  ["Zona Central"],
    "Noreste":  ["NORESTE 1", "NORESTE 2"],
    "Noroeste": ["NOROESTE 1", "NOROESTE 2"],
    "Poniente": ["PONIENTE 1", "PONIENTE 2", "PONIENTE 3"],
    "Sur":      ["SUR 1", "SUR 2", "SUR 3"],
    "Oriente":  ["ORIENTE 1", "ORIENTE 2"],
    "Sureste":  ["SURESTE 1", "SURESTE 2"],
    "Norte":    ["NORTE"],
}

# Orden del dropdown — del más cercano al más lejano (cercanía mínima del grupo,
# alfabético dentro del mismo nivel).
GRUPOS_ORDEN: list[str] = [
    "Central",   # nivel 0
    "Noreste", "Noroeste", "Poniente", "Sur",  # nivel 1
    "Oriente",   # nivel 2
    "Sureste",   # nivel 3
    "Norte",     # nivel 4
]


def grupo_de_zona(zona: str | None) -> str | None:
    """Devuelve el grupo cardinal al que pertenece una sub-zona, o None si no mapea."""
    if not zona:
        return None
    for grupo, subzonas in GRUPOS_ZONAS.items():
        if zona in subzonas:
            return grupo
    return None


def subzonas_de_grupo(grupo: str) -> list[str]:
    """Lista de sub-zonas que pertenecen a un grupo cardinal."""
    return GRUPOS_ZONAS.get(grupo, [])


def orden_zona(zona: str | None) -> int:
    """Devuelve el nivel de cercanía de una zona (0-4) o 9 si no existe."""
    return ZONA_ORDER.get(zona or "", 9)
