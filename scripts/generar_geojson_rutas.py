"""
Lee scripts/rutas_chihuahua.kml y exporta los 8 polígonos como GeoJSON.
Uso: python scripts/generar_geojson_rutas.py
"""
import json
import xml.etree.ElementTree as ET

KML_PATH = "scripts/rutas_chihuahua.kml"
OUT_PATH = "scripts/rutas_chihuahua.geojson"

NS = {"kml": "http://www.opengis.net/kml/2.2"}

COLORS = {
    "Zona Central": "#e74c3c",
    "NOROESTE": "#9b59b6",
    "NORESTE": "#2ecc71",
    "NORTE": "#3498db",
    "PONIENTE": "#f39c12",
    "SUR": "#e67e22",
    "ORIENTE": "#1abc9c",
    "SURESTE": "#34495e",
}


def parse_coordinates(text: str) -> list[list[float]]:
    """Parse KML coordinate string into [[lng, lat], ...]."""
    coords = []
    for line in text.strip().split():
        parts = line.strip().split(",")
        if len(parts) >= 2:
            lng, lat = float(parts[0]), float(parts[1])
            coords.append([lng, lat])
    return coords


def main():
    tree = ET.parse(KML_PATH)
    root = tree.getroot()

    features = []
    for placemark in root.iter(f"{{{NS['kml']}}}Placemark"):
        name_el = placemark.find(f"{{{NS['kml']}}}name")
        if name_el is None:
            continue
        name = name_el.text.strip()

        coords_el = placemark.find(f".//{{{NS['kml']}}}coordinates")
        if coords_el is None:
            continue

        coords = parse_coordinates(coords_el.text)
        if len(coords) < 3:
            continue

        # Ensure polygon is closed
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        feature = {
            "type": "Feature",
            "properties": {
                "name": name,
                "color": COLORS.get(name, "#999999"),
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            },
        }
        features.append(feature)
        print(f"  {name}: {len(coords)} vertices")

    geojson = {"type": "FeatureCollection", "features": features}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"\nExportado: {OUT_PATH} ({len(features)} zonas)")


if __name__ == "__main__":
    main()
