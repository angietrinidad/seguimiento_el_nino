"""
Descarga la ACTIVIDAD COMERCIAL del área metropolitana de Asunción desde
OpenStreetMap (Overpass API) y calcula la expuesta a la zona de inundación.

Actividad comercial = comercios (shop=*) + servicios comerciales (gastronomía,
bancos/finanzas, farmacias, combustible, oficinas, talleres/oficios) + mercados.
Es una cota INFERIOR: OSM no releva todo (subrepresenta la economía informal y los
barrios sin mapear). Fuente abierta, colaborativa.

Salidas:
- datos/geo/comercio-puntos.geojson   (todos; capa de contexto en el mapa)
- datos/geo/comercio-expuesto.geojson (los que caen en la zona de riesgo)
- datos/exposicion/comercio_resumen.json (conteos)
"""
import os, json, time, urllib.request, urllib.parse
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
EXP = os.path.join(os.path.dirname(__file__), "..", "datos", "exposicion")
BBOX = "-25.50,-57.80,-25.00,-57.28"  # (sur, oeste, norte, este): Asunción metro + Villa Hayes
AMEN = ("marketplace|bank|bureau_de_change|money_transfer|pharmacy|fuel|restaurant|"
        "cafe|fast_food|bar|pub|food_court|ice_cream|car_rental|car_wash|cinema|nightclub")
Q = f"""
[out:json][timeout:240];
(
  node["shop"]({BBOX});   way["shop"]({BBOX});
  node["office"]({BBOX}); way["office"]({BBOX});
  node["craft"]({BBOX});  way["craft"]({BBOX});
  node["amenity"~"^({AMEN})$"]({BBOX});
  way["amenity"~"^({AMEN})$"]({BBOX});
);
out center;
"""

def overpass(q):
    hosts = ("https://overpass-api.de/api/interpreter",
             "https://overpass.private.coffee/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter",
             "https://overpass.openstreetmap.ru/api/interpreter")
    for intento in range(2):
        for host in hosts:
            try:
                data = urllib.parse.urlencode({"data": q}).encode()
                req = urllib.request.Request(host, data=data, headers={
                    "User-Agent": "seguimiento-el-nino/1.0 (investigacion DRR UNA)",
                    "Accept": "application/json"})
                return json.loads(urllib.request.urlopen(req, timeout=200).read())
            except Exception as e:
                print("  fallo", host.split('/')[2], type(e).__name__, getattr(e, "code", ""))
        time.sleep(5)
    raise SystemExit("Overpass no disponible")

# categorías amplias para el tooltip/leyenda
GASTRO = {"restaurant", "cafe", "fast_food", "bar", "pub", "food_court", "ice_cream", "nightclub"}
def categoria(tags):
    s = (tags.get("shop") or "").lower()
    a = (tags.get("amenity") or "").lower()
    if a == "marketplace":
        return "Mercado"
    if a in ("bank", "bureau_de_change", "money_transfer"):
        return "Servicios financieros"
    if a == "pharmacy" or s in ("pharmacy", "chemist"):
        return "Farmacia"
    if a == "fuel":
        return "Combustible"
    if a in GASTRO:
        return "Gastronomía"
    if a in ("car_rental", "car_wash", "cinema"):
        return "Servicios comerciales"
    if tags.get("office"):
        return "Oficina / servicios"
    if tags.get("craft"):
        return "Taller / oficio"
    if s in ("supermarket", "mall", "department_store", "wholesale"):
        return "Gran superficie"
    if s in ("convenience", "kiosk", "grocery", "greengrocer", "butcher", "bakery"):
        return "Alimentos / almacén"
    if s in ("", "yes"):
        return "Comercio (sin especificar)"
    return "Comercio minorista"

res = overpass(Q)
puntos, vistos = [], set()
for el in res.get("elements", []):
    t = el.get("tags", {})
    if el["type"] == "node":
        lon, lat = el.get("lon"), el.get("lat")
    else:  # way -> center
        c = el.get("center") or {}
        lon, lat = c.get("lon"), c.get("lat")
    if lon is None or lat is None:
        continue
    clave = (round(lon, 6), round(lat, 6))
    if clave in vistos:
        continue
    vistos.add(clave)
    rubro = t.get("shop") or t.get("amenity") or t.get("office") or t.get("craft") or ""
    puntos.append({"type": "Feature",
                   "properties": {"nombre": t.get("name", ""), "tipo": categoria(t),
                                  "shop": rubro},
                   "geometry": {"type": "Point", "coordinates": [lon, lat]}})

json.dump({"type": "FeatureCollection", "features": puntos},
          open(os.path.join(GEO, "comercio-puntos.geojson"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"comercios OSM en el bbox: {len(puntos)}")

# --- expuestos en la zona de riesgo ---
zona = json.load(open(os.path.join(GEO, "zona-riesgo-inundacion.geojson"), encoding="utf-8"))
zgeom = prep(unary_union([shape(f["geometry"]) for f in zona["features"]]))
exp = [f for f in puntos if zgeom.contains(Point(*f["geometry"]["coordinates"]))]
json.dump({"type": "FeatureCollection", "features": exp},
          open(os.path.join(GEO, "comercio-expuesto.geojson"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))

from collections import Counter
por_tipo = dict(Counter(f["properties"]["tipo"] for f in exp))
resumen = {"total_bbox": len(puntos), "expuestos": len(exp), "por_tipo": por_tipo}
json.dump(resumen, open(os.path.join(EXP, "comercio_resumen.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"comercios expuestos en zona de riesgo: {len(exp)}")
print("por tipo:", por_tipo)
