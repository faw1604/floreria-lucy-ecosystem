# Security utilities
import re


def generar_codigo_referido(nombre: str, telefono: str) -> str:
    """
    Genera un código de referido único de 8 caracteres.
    Formato: primeras 3 letras del nombre (mayúsculas) + 5 últimos dígitos del teléfono.
    Ejemplo: FER43932
    """
    # Clean name: remove accents, take first 3 alpha chars
    name_clean = re.sub(r"[^a-zA-Z]", "", nombre.upper())
    prefix = (name_clean[:3] if len(name_clean) >= 3 else name_clean.ljust(3, "X"))
    # Take last 5 digits of phone
    digits = re.sub(r"\D", "", telefono)
    suffix = digits[-5:] if len(digits) >= 5 else digits.ljust(5, "0")
    return prefix + suffix
