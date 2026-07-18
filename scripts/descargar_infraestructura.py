"""
Descarga infraestructura relevante del área metropolitana de Asunción desde
OpenStreetMap (Overpass API), para dar contexto al mapa de exposición:

- DEFENSA COSTERA: la Costanera (Norte/Sur), terraplén que protege los bañados.
- VIAL: rutas troncales/primarias y puentes en la zona.

NOTA metodológica: estas obras MODULAN el riesgo real (una defensa reduce la
exposición aguas adentro), pero el mapa de huellas históricas NO ajusta por
ellas. Se muestran como capa de contexto, no como reductor cuantificado del área
inundable (haría falta la cota de protección del MOPC/Municipalidad).

Salida: datos/geo/infraestructura-asuncion.geojson
"""
import os, json, urllib.request, urllib.parse

# bbox Overpass: (sur, oeste, norte, este)
BBOX = "-25.46,-57.78,-25.00,-57.28"
Q = f"""
[out:json][timeout:90];
(
  way["name"~"Costanera",i]["highway"]({BBOX});
  way["highway"~"^(trunk|primary)$"]({BBOX});
  way["bridge"="yes"]["highway"]({BBOX});
);
out geom;
"""
GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")

def overpass(q):
    hosts = ("https://overpass-api.de/api/interpreter",
             "https://overpass.private.coffee/api/interpreter",
             "https://overpass.openstreetmap.ru/api/interpreter",
             "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter")
    import time
    for intento in range(2):
      for host in hosts:
        try:
            data = urllib.parse.urlencode({"data": q}).encode()
            req = urllib.request.Request(host, data=data, headers={
                "User-Agent": "seguimiento-el-nino/1.0 (investigación DRR UNA)",
                "Accept": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=120).read())
        except Exception as e:
            print("  fallo", host.split('/')[2], type(e).__name__, getattr(e, "code", ""))
      time.sleep(5)
    raise SystemExit("Overpass no disponible")

res = overpass(Q)
feats = []
for el in res.get("elements", []):
    if el.get("type") != "way" or "geometry" not in el:
        continue
    t = el.get("tags", {})
    nombre = t.get("name", "")
    es_costanera = "costanera" in nombre.lower()
    categoria = "Defensa costera (Costanera)" if es_costanera else (
        "Puente" if t.get("bridge") == "yes" else "Ruta principal")
    coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
    if len(coords) < 2:
        continue
    feats.append({"type": "Feature",
                  "properties": {"nombre": nombre or categoria, "categoria": categoria,
                                 "highway": t.get("highway"), "puente": t.get("bridge") == "yes"},
                  "geometry": {"type": "LineString", "coordinates": coords}})

out = os.path.join(GEO, "infraestructura-asuncion.geojson")
json.dump({"type": "FeatureCollection",
           "metadata": {"fuente": "OpenStreetMap (Overpass)", "bbox": BBOX,
                        "nota": "Contexto; el mapa no ajusta el área inundable por estas obras"},
           "features": feats}, open(out, "w", encoding="utf-8"), separators=(",", ":"))
from collections import Counter
print("elementos:", len(feats))
for c, n in Counter(f["properties"]["categoria"] for f in feats).most_common():
    print(f"  {c}: {n}")
print("costanera nombres:", sorted({f["properties"]["nombre"] for f in feats if "Costanera" in f["properties"]["categoria"]})[:6])
