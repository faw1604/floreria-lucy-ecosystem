"""
Lee scripts/zonas_envio.kml y exporta los 3 polígonos de zona de envío como GeoJSON.
Cada carpeta del KML puede tener múltiples Placemarks y MultiGeometry.
Se unen con unary_union por zona.

Uso: python scripts/generar_geojson_zonas.py
"""
import json
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon, MultiPolygon, mapping
from shapely.ops import unary_union

KML_PATH = "scripts/zonas_envio.kml"
OUT_PATH = "scripts/zonas_envio.geojson"

NS = {"kml": "http://www.opengis.net/kml/2.2"}

ZONE_MAP = {
    "Zona morada ($99)": {"nombre": "Morada", "tarifa": 99, "color": "#7c3aed"},
    "Zona Azul ($159)": {"nombre": "Azul", "tarifa": 159, "color": "#2563eb"},
    "Zona verde ($199)": {"nombre": "Verde", "tarifa": 199, "color": "#16a34a"},
}


def parse_coordinates(text):
    coords = []
    for line in text.strip().split():
        parts = line.strip().split(",")
        if len(parts) >= 2:
            coords.append((float(parts[0]), float(parts[1])))
    return coords


def extract_polygons(element):
    """Extract all Polygon geometries from an element (handles MultiGeometry)."""
    polys = []
    for poly_el in element.iter(f"{{{NS['kml']}}}Polygon"):
        coords_el = poly_el.find(f".//{{{NS['kml']}}}coordinates")
        if coords_el is None:
            continue
        coords = parse_coordinates(coords_el.text)
        if len(coords) >= 3:
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            polys.append(Polygon(coords))
    return polys


def main():
    tree = ET.parse(KML_PATH)
    root = tree.getroot()

    features = []

    for folder in root.iter(f"{{{NS['kml']}}}Folder"):
        name_el = folder.find(f"{{{NS['kml']}}}name")
        if name_el is None:
            continue
        folder_name = name_el.text.strip()

        zone_info = ZONE_MAP.get(folder_name)
        if not zone_info:
            print(f"  Carpeta ignorada: {folder_name}")
            continue

        all_polys = []
        for placemark in folder.findall(f"{{{NS['kml']}}}Placemark"):
            pm_name = placemark.find(f"{{{NS['kml']}}}name")
            pm_label = pm_name.text.strip() if pm_name is not None else "?"
            polys = extract_polygons(placemark)
            print(f"  {folder_name} > {pm_label}: {len(polys)} poligono(s)")
            all_polys.extend(polys)

        if not all_polys:
            print(f"  ADVERTENCIA: {folder_name} sin poligonos")
            continue

        merged = unary_union(all_polys)

        feature = {
            "type": "Feature",
            "properties": {
                "nombre": zone_info["nombre"],
                "tarifa": zone_info["tarifa"],
                "color": zone_info["color"],
            },
            "geometry": mapping(merged),
        }
        features.append(feature)
        n_verts = sum(len(p.exterior.coords) for p in (merged.geoms if isinstance(merged, MultiPolygon) else [merged]))
        print(f"  -> {zone_info['nombre']}: {n_verts} vertices totales")

    geojson = {"type": "FeatureCollection", "features": features}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"\nExportado: {OUT_PATH} ({len(features)} zonas)")


if __name__ == "__main__":
    main()
