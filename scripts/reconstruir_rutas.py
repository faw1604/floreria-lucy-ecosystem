"""
Reconstruir los 8 polígonos de zonas de reparto de Chihuahua
a partir de las líneas divisorias extraídas del KML (RUTAS_FECHAS_FUERTES.kmz).

La zona Central ya tiene su polígono completo del KML.
Las 7 zonas restantes se reconstruyen usando las líneas divisorias
y un bounding box exterior de Chihuahua como borde natural.

Exporta: scripts/rutas_chihuahua.geojson
"""
import json
import math
from shapely.geometry import Polygon, MultiPolygon, LineString, box, Point, mapping
from shapely.ops import split, unary_union

# ─── Bounding box de Chihuahua ───
BBOX = box(-106.25, 28.55, -105.92, 28.83)

# ─── Centro aproximado de la ciudad ───
CENTER = (-106.089, 28.635)

# ─── Polígono Central (extraído directamente del KML) ───
CENTRAL_COORDS = [
    (-106.1035, 28.6450),
    (-106.0960, 28.6480),
    (-106.0870, 28.6470),
    (-106.0790, 28.6445),
    (-106.0740, 28.6400),
    (-106.0720, 28.6340),
    (-106.0730, 28.6280),
    (-106.0770, 28.6230),
    (-106.0840, 28.6200),
    (-106.0930, 28.6195),
    (-106.1010, 28.6210),
    (-106.1060, 28.6260),
    (-106.1080, 28.6320),
    (-106.1070, 28.6390),
    (-106.1035, 28.6450),
]
CENTRAL_POLY = Polygon(CENTRAL_COORDS)

# ─── Líneas divisorias del KML ───
# Cada línea va desde un punto cercano al borde del Central
# hasta el borde del bounding box, dividiendo las zonas exteriores.
# Los ángulos corresponden a las divisiones entre zonas del KML.

# Angulos de las divisiones (grados desde el este, antihorario):
#   Norte/Noreste:  ~58°
#   Noreste/Oriente: ~20°
#   Oriente/Sureste: ~340° (=-20°)
#   Sureste/Sur:     ~245°
#   Sur/Poniente:    ~215°
#   Poniente/Noroeste: ~148°
#   Noroeste/Norte:  ~105°

DIVISION_ANGLES_DEG = [58, 20, 340, 245, 215, 148, 105]

# Zonas en orden antihorario, empezando desde el ángulo más bajo (20°=Noreste/Oriente)
# El sector entre angle[i] y angle[i+1] define una zona.
# Ordenamos los ángulos y asignamos nombres:
ZONE_DEFINITIONS = [
    # (start_angle, end_angle, name)
    # Going counterclockwise from 20° to 58°
    (20, 58, "Noreste"),
    (58, 105, "Norte"),
    (105, 148, "Noroeste"),
    (148, 215, "Poniente"),
    (215, 245, "Sur"),
    (245, 340, "Sureste"),
    (340, 380, "Oriente"),  # 340 to 360+20 = wraps around
]


def angle_ray(center, angle_deg, length=0.5):
    """Create a line from center outward at given angle (degrees from east)."""
    rad = math.radians(angle_deg)
    dx = length * math.cos(rad)
    dy = length * math.sin(rad)
    return LineString([center, (center[0] + dx, center[1] + dy)])


def make_sector(center, a_start, a_end, radius=0.5, steps=30):
    """Create a pie-slice polygon from center between two angles."""
    coords = [center]
    # Handle wraparound
    if a_end <= a_start:
        a_end += 360

    for i in range(steps + 1):
        a = math.radians(a_start + (a_end - a_start) * i / steps)
        x = center[0] + radius * math.cos(a)
        y = center[1] + radius * math.sin(a)
        coords.append((x, y))
    coords.append(center)
    return Polygon(coords)


def build_zones():
    """Build all 8 zone polygons."""
    zones = {}

    # Central — already complete
    zones["Central"] = CENTRAL_POLY

    # Outer ring = bbox minus central
    outer_ring = BBOX.difference(CENTRAL_POLY)

    # Build each outer zone as a sector intersected with the outer ring
    for a_start, a_end, name in ZONE_DEFINITIONS:
        sector = make_sector(CENTER, a_start, a_end, radius=0.5, steps=40)
        zone_poly = sector.intersection(outer_ring)

        # Clean up: keep only polygons, drop tiny slivers
        if isinstance(zone_poly, MultiPolygon):
            parts = [p for p in zone_poly.geoms if p.area > 1e-8]
            zone_poly = parts[0] if len(parts) == 1 else MultiPolygon(parts)

        if not zone_poly.is_empty:
            zones[name] = zone_poly

    return zones


def to_geojson(zones):
    """Convert zones dict to GeoJSON FeatureCollection."""
    colors = {
        "Central": "#e74c3c",
        "Norte": "#3498db",
        "Noreste": "#2ecc71",
        "Noroeste": "#9b59b6",
        "Poniente": "#f39c12",
        "Oriente": "#1abc9c",
        "Sur": "#e67e22",
        "Sureste": "#34495e",
    }

    features = []
    for name, poly in zones.items():
        feature = {
            "type": "Feature",
            "properties": {
                "name": name,
                "color": colors.get(name, "#999999"),
            },
            "geometry": mapping(poly),
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def main():
    print("Reconstruyendo zonas de reparto...")
    zones = build_zones()

    for name, poly in zones.items():
        area_km2 = poly.area * 111 * 111  # rough deg->km
        print(f"  {name}: {area_km2:.1f} km2 aprox")

    geojson = to_geojson(zones)
    out_path = "scripts/rutas_chihuahua.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"\nExportado: {out_path} ({len(geojson['features'])} zonas)")

    # Generate preview HTML
    generate_preview(geojson)


def generate_preview(geojson):
    """Generate standalone Leaflet preview HTML with embedded GeoJSON."""
    geojson_str = json.dumps(geojson, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rutas de reparto — Chihuahua</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body {{ margin: 0; font-family: Arial, sans-serif; }}
  #map {{ width: 100%; height: 100vh; }}
  .zone-label {{
    background: none; border: none; box-shadow: none;
    font-size: 13px; font-weight: 700; color: #333;
    text-shadow: 1px 1px 2px #fff, -1px -1px 2px #fff, 1px -1px 2px #fff, -1px 1px 2px #fff;
    white-space: nowrap;
  }}
</style>
</head>
<body>
<div id="map"></div>
<script>
const geojson = {geojson_str};

const map = L.map('map').setView([28.635, -106.089], 12);

L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 18
}}).addTo(map);

L.geoJSON(geojson, {{
  style: function(feature) {{
    return {{
      fillColor: feature.properties.color,
      fillOpacity: 0.25,
      color: feature.properties.color,
      weight: 2,
      opacity: 0.8
    }};
  }},
  onEachFeature: function(feature, layer) {{
    // Add zone name label at centroid
    const bounds = layer.getBounds();
    const center = bounds.getCenter();
    const label = L.divIcon({{
      className: 'zone-label',
      html: feature.properties.name,
      iconSize: [100, 20],
      iconAnchor: [50, 10]
    }});
    L.marker(center, {{ icon: label }}).addTo(map);

    layer.bindPopup('<strong>' + feature.properties.name + '</strong>');
  }}
}}).addTo(map);
</script>
</body>
</html>"""

    out_path = "scripts/rutas_preview.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Exportado: {out_path}")


if __name__ == "__main__":
    main()
