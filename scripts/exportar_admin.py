"""
Exporta la lista individualizada de establecimientos expuestos a una planilla
LOCAL (CSV) que NO se publica (la carpeta admin-privado/ está en .gitignore).

Úsalo si querés mantener estos datos fuera del sitio público:
    python scripts/exportar_admin.py

Salida: admin-privado/expuestos.csv
"""
import os, csv, json

GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "admin-privado")
os.makedirs(OUT_DIR, exist_ok=True)

feats = json.load(open(os.path.join(GEO, "expuestos-inundacion.geojson"), encoding="utf-8"))["features"]
out = os.path.join(OUT_DIR, "expuestos.csv")
with open(out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["zona", "clase", "nombre", "tipo", "lat", "lon", "osm_url"])
    for ft in feats:
        p = ft["properties"]
        lon, lat = ft["geometry"]["coordinates"]
        w.writerow([p.get("zona", ""), p.get("clase", ""), p.get("nombre", ""), p.get("tipo", ""),
                    lat, lon, f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"])
print(f"exportado: {os.path.normpath(out)} ({len(feats)} establecimientos)")
