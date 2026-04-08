"""
Geocodificación de direcciones en Chihuahua.
Usa Google Geocoding API si GOOGLE_GEOCODING_KEY está configurada,
fallback a Nominatim (OpenStreetMap) si no.
"""
import os
import logging
import httpx

logger = logging.getLogger("floreria")

GOOGLE_KEY = os.getenv("GOOGLE_GEOCODING_KEY", "")

# Bounding box de Chihuahua ciudad
LAT_MIN, LAT_MAX = 28.55, 28.83
LNG_MIN, LNG_MAX = -106.25, -105.92


def _in_chihuahua(lat: float, lng: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX


async def geocodificar(direccion: str) -> dict | None:
    """
    Geocodifica una dirección en Chihuahua.
    Retorna {"lat": float, "lng": float, "display_name": str} o None.
    """
    if GOOGLE_KEY:
        return await _google_geocode(direccion)
    return await _nominatim_geocode(direccion)


async def _google_geocode(direccion: str) -> dict | None:
    """Google Geocoding API — preciso para México."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": f"{direccion}, Chihuahua, Chihuahua, Mexico",
        "key": GOOGLE_KEY,
        "bounds": f"{LAT_MIN},{LNG_MIN}|{LAT_MAX},{LNG_MAX}",
        "region": "mx",
        "language": "es",
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=params, timeout=10)
            data = r.json()

        if data.get("status") != "OK" or not data.get("results"):
            logger.warning(f"[GEO] Google no result: {data.get('status')}")
            return None

        result = data["results"][0]
        loc = result["geometry"]["location"]
        lat, lng = loc["lat"], loc["lng"]

        if not _in_chihuahua(lat, lng):
            logger.warning(f"[GEO] Google result outside Chihuahua: {lat}, {lng}")
            return None

        logger.info(f"[GEO] Google: {lat}, {lng} — {result.get('formatted_address', '')}")
        return {
            "lat": lat,
            "lng": lng,
            "display_name": result.get("formatted_address", ""),
        }
    except Exception as e:
        logger.error(f"[GEO] Google error: {e}")
        return None


async def autocomplete(texto: str) -> list[dict]:
    """
    Google Places Autocomplete — retorna lista de sugerencias.
    Cada una: {"description": "Calle Sexta 2209, ...", "place_id": "ChIJ..."}
    Si no hay Google key, retorna lista vacía.
    """
    if not GOOGLE_KEY:
        return []
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": texto,
        "key": GOOGLE_KEY,
        "types": "address",
        "language": "es",
        "components": "country:mx",
        "location": f"{(LAT_MIN+LAT_MAX)/2},{(LNG_MIN+LNG_MAX)/2}",
        "radius": "20000",
        "strictbounds": "true",
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=params, timeout=5)
            data = r.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.warning(f"[GEO] Autocomplete error: {data.get('status')}")
            return []
        return [
            {"description": p["description"], "place_id": p["place_id"]}
            for p in data.get("predictions", [])[:5]
        ]
    except Exception as e:
        logger.error(f"[GEO] Autocomplete error: {e}")
        return []


async def place_details(place_id: str) -> dict | None:
    """
    Obtiene lat/lng de un place_id de Google.
    Retorna {"lat": float, "lng": float, "display_name": str} o None.
    """
    if not GOOGLE_KEY:
        return None
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": GOOGLE_KEY,
        "fields": "geometry,formatted_address",
        "language": "es",
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=params, timeout=5)
            data = r.json()
        if data.get("status") != "OK":
            return None
        result = data["result"]
        loc = result["geometry"]["location"]
        lat, lng = loc["lat"], loc["lng"]
        if not _in_chihuahua(lat, lng):
            logger.warning(f"[GEO] Place outside Chihuahua: {lat}, {lng}")
            return None
        return {
            "lat": lat,
            "lng": lng,
            "display_name": result.get("formatted_address", ""),
        }
    except Exception as e:
        logger.error(f"[GEO] Place details error: {e}")
        return None


async def _nominatim_geocode(direccion: str) -> dict | None:
    """Nominatim (OpenStreetMap) — fallback gratuito."""
    import re
    ua = "FloreriaLucy/1.0 florerialucychihuahua@gmail.com"
    calle = direccion.split(",")[0].strip()
    calle_exp = re.sub(r"(?i)^C\.\s*", "Calle ", calle)
    calle_exp = re.sub(r"(?i)^Av\.\s*", "Avenida ", calle_exp)
    calle_exp = re.sub(r"(?i)^Blvd\.\s*", "Boulevard ", calle_exp)

    vb = f"{LNG_MIN},{LAT_MAX},{LNG_MAX},{LAT_MIN}"

    async def _nom(params):
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params=params, headers={"User-Agent": ua}, timeout=10,
            )
            return r.json()

    def _valid(data):
        if not data:
            return False
        return _in_chihuahua(float(data[0]["lat"]), float(data[0]["lon"]))

    try:
        # 1) Structured: street + city
        data = await _nom({
            "street": calle_exp, "city": "Chihuahua", "state": "Chihuahua",
            "country": "Mexico", "countrycodes": "mx", "bounded": "1",
            "viewbox": vb, "format": "json", "limit": "1",
        })
        # 2) Free-form with street only
        if not _valid(data):
            data = await _nom({
                "q": f"{calle_exp}, Chihuahua, Mexico",
                "countrycodes": "mx", "bounded": "1", "viewbox": vb,
                "format": "json", "limit": "1",
            })
        # 3) Full address
        if not _valid(data):
            data = await _nom({
                "q": f"{direccion}, Chihuahua, Mexico",
                "countrycodes": "mx", "bounded": "1", "viewbox": vb,
                "format": "json", "limit": "1",
            })

        if not _valid(data):
            return None

        lat = float(data[0]["lat"])
        lng = float(data[0]["lon"])
        logger.info(f"[GEO] Nominatim: {lat}, {lng}")
        return {
            "lat": lat,
            "lng": lng,
            "display_name": data[0].get("display_name", ""),
        }
    except Exception as e:
        logger.error(f"[GEO] Nominatim error: {e}")
        return None
