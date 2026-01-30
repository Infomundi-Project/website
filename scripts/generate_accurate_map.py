#!/usr/bin/env python3
"""
Generate accurate world map SVG with realistic borders from Natural Earth 10m data.
Uses Robinson projection and Douglas-Peucker simplification for web optimization.
"""

import json
import math
import os
from datetime import datetime

# Robinson projection parameters
ROBINSON_AA = [
    0.8487, 0.84751182, 0.84479598, 0.840213, 0.83359314, 0.8257851, 0.814752, 0.80006949,
    0.78216192, 0.76060494, 0.73658673, 0.7086645, 0.67777182, 0.64475739, 0.60987582,
    0.57134484, 0.52729731, 0.48562614, 0.45167814
]
ROBINSON_BB = [
    0, 0.0838426, 0.1676852, 0.2515278, 0.3353704, 0.419213, 0.5030556, 0.5868982,
    0.67182264, 0.75336633, 0.83518048, 0.91537187, 0.99339958, 1.06872269, 1.14066505,
    1.20841528, 1.27035062, 1.31998003, 1.3523
]

# Region mapping for all countries
REGION_MAPPING = {
    "north-america": ["US", "CA", "GL"],
    "central-america": ["MX", "GT", "BZ", "HN", "SV", "NI", "CR", "PA", "CU", "JM", "HT", "DO", "PR", "TT", "BS", "BB", "LC", "GD", "VC", "AG", "DM", "KN", "AW", "CW", "SX", "BQ", "TC", "VG", "VI", "AI", "MS", "GP", "MQ", "BL", "MF", "KY"],
    "south-america": ["CO", "VE", "GY", "SR", "GF", "EC", "PE", "BR", "BO", "PY", "CL", "AR", "UY", "FK"],
    "europe": ["IS", "PT", "ES", "GB", "IE", "FR", "BE", "NL", "LU", "DE", "CH", "LI", "AT", "IT", "SM", "VA", "MC", "MT", "AD", "SI", "HR", "BA", "ME", "RS", "XK", "AL", "MK", "GR", "BG", "RO", "HU", "SK", "CZ", "PL", "DK", "NO", "SE", "FI", "EE", "LV", "LT", "BY", "UA", "MD", "CY", "FO", "GG", "JE", "IM", "GI", "AX"],
    "asia": ["RU", "KZ", "UZ", "TM", "KG", "TJ", "MN", "CN", "TW", "KP", "KR", "JP", "GE", "AM", "AZ", "TR", "SY", "LB", "IL", "PS", "JO", "IQ", "IR", "KW", "SA", "BH", "QA", "AE", "OM", "YE", "AF", "PK", "IN", "NP", "BT", "BD", "MM", "TH", "LA", "VN", "KH", "MY", "SG", "BN", "ID", "TL", "PH", "MV", "LK", "HK", "MO"],
    "africa": ["MA", "DZ", "TN", "LY", "EG", "EH", "MR", "ML", "NE", "TD", "SD", "SS", "ER", "DJ", "SO", "ET", "SN", "GM", "GW", "GN", "SL", "LR", "CI", "BF", "GH", "TG", "BJ", "NG", "CM", "CF", "GQ", "GA", "CG", "CD", "UG", "KE", "RW", "BI", "TZ", "AO", "ZM", "MW", "MZ", "ZW", "BW", "NA", "ZA", "LS", "SZ", "MG", "KM", "SC", "MU", "CV", "ST", "RE", "YT"],
    "oceania": ["AU", "NZ", "PG", "FJ", "SB", "VU", "NC", "WS", "TO", "FM", "MH", "PW", "KI", "NR", "TV", "CK", "NU", "TK", "AS", "GU", "MP", "PF", "WF", "PN"]
}

# Invert mapping for quick lookup
COUNTRY_TO_REGION = {}
for region, countries in REGION_MAPPING.items():
    for country in countries:
        COUNTRY_TO_REGION[country] = region

# Region colors
REGION_COLORS = {
    "north-america": "#2aa0ff",
    "central-america": "#ff6b35",
    "south-america": "#7b5cff",
    "europe": "#ff8c42",
    "asia": "#00c2ff",
    "africa": "#ff3b30",
    "oceania": "#34c759"
}

# Region viewbox for zoom
REGION_VIEWBOX = {
    "north-america": "80 50 280 200",
    "central-america": "120 160 200 150",
    "south-america": "180 220 200 280",
    "europe": "420 60 200 200",
    "asia": "500 50 450 250",
    "africa": "400 150 250 300",
    "oceania": "700 250 280 200"
}

# Microstate minimum size (in SVG units)
MICROSTATE_MIN_SIZE = 3

def robinson_project(lon, lat):
    """Project lat/lon to Robinson projection coordinates."""
    abs_lat = abs(lat)
    idx = int(abs_lat / 5)
    if idx >= 18:
        idx = 17
    frac = (abs_lat - idx * 5) / 5

    aa = ROBINSON_AA[idx] + frac * (ROBINSON_AA[idx + 1] - ROBINSON_AA[idx]) if idx < 18 else ROBINSON_AA[18]
    bb = ROBINSON_BB[idx] + frac * (ROBINSON_BB[idx + 1] - ROBINSON_BB[idx]) if idx < 18 else ROBINSON_BB[18]

    x = 0.8487 * aa * lon
    y = bb * 90 * (1 if lat >= 0 else -1)

    # Scale and translate to SVG viewport (1000x500)
    svg_x = (x + 180 * 0.8487) * (1000 / (360 * 0.8487))
    svg_y = 250 - y * (500 / (180 * 1.3523))

    return svg_x, svg_y

def perpendicular_distance(point, line_start, line_end):
    """Calculate perpendicular distance from point to line."""
    if line_start == line_end:
        return math.sqrt((point[0] - line_start[0])**2 + (point[1] - line_start[1])**2)

    dx = line_end[0] - line_start[0]
    dy = line_end[1] - line_start[1]

    t = max(0, min(1, ((point[0] - line_start[0]) * dx + (point[1] - line_start[1]) * dy) / (dx * dx + dy * dy)))

    proj_x = line_start[0] + t * dx
    proj_y = line_start[1] + t * dy

    return math.sqrt((point[0] - proj_x)**2 + (point[1] - proj_y)**2)

def douglas_peucker(points, epsilon):
    """Simplify a polyline using the Douglas-Peucker algorithm."""
    if len(points) < 3:
        return points

    # Find the point with maximum distance
    max_dist = 0
    max_idx = 0

    for i in range(1, len(points) - 1):
        dist = perpendicular_distance(points[i], points[0], points[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    # If max distance is greater than epsilon, recursively simplify
    if max_dist > epsilon:
        left = douglas_peucker(points[:max_idx + 1], epsilon)
        right = douglas_peucker(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]

def simplify_ring(ring, epsilon=0.5):
    """Simplify a ring of coordinates."""
    if len(ring) < 4:
        # Project directly without simplification
        return [robinson_project(lon, lat) for lon, lat in ring]

    # Project to SVG coordinates first
    projected = [robinson_project(lon, lat) for lon, lat in ring]

    # Simplify
    simplified = douglas_peucker(projected, epsilon)

    # Ensure minimum points for a polygon (3 for triangle)
    if len(simplified) < 3:
        # Return simplified with just start and end if too few points
        return [projected[0], projected[len(projected)//2], projected[-1]]

    return simplified

def geometry_to_path(geometry, epsilon=0.5):
    """Convert GeoJSON geometry to SVG path string."""
    geom_type = geometry["type"]
    coords = geometry["coordinates"]

    paths = []

    if geom_type == "Polygon":
        for ring in coords:
            simplified = simplify_ring(ring, epsilon)
            if len(simplified) >= 3:
                path_str = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in simplified) + "Z"
                paths.append(path_str)

    elif geom_type == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                simplified = simplify_ring(ring, epsilon)
                if len(simplified) >= 3:
                    path_str = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in simplified) + "Z"
                    paths.append(path_str)

    return " ".join(paths)

def get_country_bounds(geometry):
    """Get bounding box of a geometry in SVG coordinates."""
    geom_type = geometry["type"]
    coords = geometry["coordinates"]

    all_points = []

    if geom_type == "Polygon":
        for ring in coords:
            for lon, lat in ring:
                all_points.append(robinson_project(lon, lat))
    elif geom_type == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                for lon, lat in ring:
                    all_points.append(robinson_project(lon, lat))

    if not all_points:
        return None

    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]

    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
        "center_x": (min(xs) + max(xs)) / 2,
        "center_y": (min(ys) + max(ys)) / 2
    }

def create_microstate_path(bounds, min_size=MICROSTATE_MIN_SIZE):
    """Create a visible marker for very small countries."""
    cx = bounds["center_x"]
    cy = bounds["center_y"]
    # Ensure minimum radius of 2px for visibility
    r = max(2.0, min_size / 2, max(bounds["width"], bounds["height"]) / 2)

    # Create a circle-like path using arc commands
    return f"M{cx-r:.1f},{cy:.1f}A{r:.1f},{r:.1f} 0 1,0 {cx+r:.1f},{cy:.1f}A{r:.1f},{r:.1f} 0 1,0 {cx-r:.1f},{cy:.1f}Z"

def load_geojson(filepath):
    """Load and parse GeoJSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_svg(geojson_data, output_path):
    """Generate the world map SVG from GeoJSON data."""

    # First pass: collect all features by ISO code to handle duplicates
    country_features = {}  # iso_code -> list of features

    for feature in geojson_data["features"]:
        props = feature["properties"]
        geometry = feature["geometry"]

        # Get ISO code (prefer ISO_A2_EH which includes all territories)
        iso_code = props.get("ISO_A2_EH") or props.get("ISO_A2")
        if iso_code == "-99" or not iso_code:
            # Try ADM0_A3 as fallback
            adm0 = props.get("ADM0_A3", "")
            if adm0 == "KOS":
                iso_code = "XK"  # Kosovo
            elif adm0 == "PSX":
                iso_code = "PS"  # Palestine
            elif adm0 == "SAH":
                iso_code = "EH"  # Western Sahara
            else:
                continue  # Skip unknown territories

        if iso_code not in country_features:
            country_features[iso_code] = {
                "name": props.get("NAME_LONG") or props.get("NAME") or props.get("ADMIN", "Unknown"),
                "geometries": []
            }
        country_features[iso_code]["geometries"].append(geometry)

    # Organize countries by region
    regions = {region: [] for region in REGION_MAPPING.keys()}
    unknown_region = []

    for iso_code, data in country_features.items():
        name = data["name"]
        geometries = data["geometries"]

        # Calculate combined bounds from all geometries
        all_bounds = []
        for geom in geometries:
            b = get_country_bounds(geom)
            if b:
                all_bounds.append(b)

        if all_bounds:
            combined_bounds = {
                "min_x": min(b["min_x"] for b in all_bounds),
                "max_x": max(b["max_x"] for b in all_bounds),
                "min_y": min(b["min_y"] for b in all_bounds),
                "max_y": max(b["max_y"] for b in all_bounds),
            }
            combined_bounds["width"] = combined_bounds["max_x"] - combined_bounds["min_x"]
            combined_bounds["height"] = combined_bounds["max_y"] - combined_bounds["min_y"]
            combined_bounds["center_x"] = (combined_bounds["min_x"] + combined_bounds["max_x"]) / 2
            combined_bounds["center_y"] = (combined_bounds["min_y"] + combined_bounds["max_y"]) / 2
        else:
            combined_bounds = None

        # Get region
        region = COUNTRY_TO_REGION.get(iso_code)
        if not region and combined_bounds:
            # Try to determine region by coordinates
            cx = combined_bounds["center_x"]
            cy = combined_bounds["center_y"]
            # Simple heuristic based on position
            if cx < 350:
                if cy < 200:
                    region = "north-america"
                elif cy < 300:
                    region = "central-america"
                else:
                    region = "south-america"
            elif cx < 600:
                if cy < 300:
                    region = "europe"
                else:
                    region = "africa"
            elif cx < 850:
                region = "asia"
            else:
                region = "oceania"

        if not region:
            unknown_region.append((iso_code, name))
            continue

        # Determine simplification level based on country size
        if combined_bounds:
            country_size = max(combined_bounds["width"], combined_bounds["height"])
            if country_size < 5:
                epsilon = 0.1  # Very low simplification for small countries
            elif country_size < 20:
                epsilon = 0.3  # Low simplification for medium countries
            else:
                epsilon = 1.0  # Normal simplification for large countries
        else:
            epsilon = 1.0

        # Generate combined path from all geometries
        all_paths = []
        for geom in geometries:
            path = geometry_to_path(geom, epsilon=epsilon)
            if path:
                all_paths.append(path)

        combined_path = " ".join(all_paths)

        # For very tiny countries that may have been simplified to near nothing, create a visible marker
        if combined_bounds:
            path_size = max(combined_bounds["width"], combined_bounds["height"])
            # If the country is too small to be visible, use a circular marker
            if path_size < 5 or (combined_path and len(combined_path) < 50):
                combined_path = create_microstate_path(combined_bounds, min_size=5)

        if combined_path:
            regions[region].append({
                "iso": iso_code,
                "name": name,
                "path": combined_path,
                "bounds": combined_bounds
            })

    # Print unknown countries
    if unknown_region:
        print(f"Warning: {len(unknown_region)} countries without region assignment:")
        for iso, name in unknown_region[:10]:
            print(f"  {iso}: {name}")

    # Generate SVG
    timestamp = datetime.now().strftime("%a %b %d %H:%M:%S UTC %Y")
    total_countries = sum(len(countries) for countries in regions.values())

    svg_parts = []

    # Header
    svg_parts.append(f"""<!-- MAPA ATUALIZADO: {timestamp} - {total_countries} PAISES -->
<button id="map-back-btn" class="map-back-btn" aria-label="Return to world view" style="display: none;">
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M8 2L4 6L8 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
  <span>Back</span>
</button>
<svg id="world-map"
     viewBox="0 0 1000 500"
     xmlns="http://www.w3.org/2000/svg"
     role="img"
     aria-label="Interactive world map. Click a continent to see countries.">
  <defs>
    <linearGradient id="water-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#e8f4fc;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#d0e8f7;stop-opacity:1" />
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.3"/>
    </filter>
  </defs>

  <rect x="0" y="0" width="1000" height="500" fill="url(#water-gradient)" class="water-bg"/>
""")

    # Continents layer (for world view)
    svg_parts.append('  <g id="continents" class="map-layer continents-layer">')

    for region_id, countries in regions.items():
        if not countries:
            continue
        color = REGION_COLORS.get(region_id, "#888888")
        region_name = region_id.replace("-", " ").title()

        # Combine all country paths for the continent
        all_paths = " ".join(c["path"] for c in countries)

        svg_parts.append(f'''    <a href="#{region_id}" class="continent" data-region="{region_id}" data-color="{color}" aria-label="{region_name}. Click to view countries.">
      <path d="{all_paths}"/>
    </a>''')

    svg_parts.append('  </g>')

    # Country layers (for zoomed view)
    for region_id, countries in regions.items():
        if not countries:
            continue
        color = REGION_COLORS.get(region_id, "#888888")
        viewbox = REGION_VIEWBOX.get(region_id, "0 0 1000 500")
        region_name = region_id.replace("-", " ").title()

        svg_parts.append(f'''
  <g id="{region_id}" class="map-layer country-layer" data-region="{region_id}" data-viewbox="{viewbox}" data-color="{color}" role="list" aria-label="{region_name} countries">
    <g class="other-regions" aria-hidden="true">
      <!-- Other regions shown faded when this region is zoomed -->
    </g>''')

        # Sort countries by name for consistent ordering
        countries.sort(key=lambda c: c["name"])

        for country in countries:
            svg_parts.append(f'''    <a href="/news?country={country["iso"]}" class="country" data-country="{country["iso"]}" data-region="{region_id}" role="listitem" aria-label="{country["name"]}. Click to view news.">
      <path d="{country["path"]}"/>
      <title>{country["name"]}</title>
    </a>''')

        svg_parts.append('  </g>')

    # Footer
    svg_parts.append('</svg>')

    # Write output
    svg_content = "\n".join(svg_parts)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(svg_content)

    print(f"Generated SVG with {total_countries} countries")
    print(f"Output: {output_path}")
    print(f"Size: {len(svg_content) / 1024:.1f} KB")

    # Print statistics per region
    print("\nCountries per region:")
    for region_id, countries in regions.items():
        print(f"  {region_id}: {len(countries)}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    geojson_path = os.path.join(project_dir, "assets", "data", "geojson", "countries_10m.geojson")
    output_path = os.path.join(project_dir, "templates", "components", "world-map.html")

    if not os.path.exists(geojson_path):
        print(f"Error: GeoJSON file not found: {geojson_path}")
        print("Please download Natural Earth 10m data first.")
        return 1

    print(f"Loading GeoJSON: {geojson_path}")
    geojson_data = load_geojson(geojson_path)
    print(f"Loaded {len(geojson_data['features'])} features")

    print("\nGenerating SVG...")
    generate_svg(geojson_data, output_path)

    return 0

if __name__ == "__main__":
    exit(main())
