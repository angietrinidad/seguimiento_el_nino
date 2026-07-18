"""
Descarga el registro OFICIAL de establecimientos de salud georreferenciados del
MSPBS (DIGIES), publicado como un mapa de Google My Maps, y lo convierte a GeoJSON.

El visor de https://digies.mspbs.gov.py/establecimientos-de-salud-georeferenciados/
embebe un Google My Maps (mid=1mI_0GojV6ky3oqiF-fMhDePoElIezIMk), exportable como
KML. Cada carpeta del mapa es una CATEGORÍA oficial (USF, puesto, centro, hospital
distrital/regional/nacional/especializado), y cada punto trae departamento,
distrito, tipo y coordenadas.

Salida: datos/oficial/mspbs_salud.geojson (1.057 establecimientos).
"""
import os, re, json, urllib.request
import xml.etree.ElementTree as ET

MID = "1mI_0GojV6ky3oqiF-fMhDePoElIezIMk"
OUT = os.path.join(os.path.dirname(__file__), "..", "datos", "oficial")
os.makedirs(OUT, exist_ok=True)
KML = os.path.join(OUT, "mspbs_salud.kml")
NS = {"k": "http://www.opengis.net/kml/2.2"}

if not os.path.exists(KML):
    url = f"https://www.google.com/maps/d/kml?mid={MID}&forcekml=1"
    open(KML, "wb").write(urllib.request.urlopen(url, timeout=90).read())

def campo(desc, clave):
    m = re.search(clave + r":\s*([^<]+)", desc or "")
    return m.group(1).strip() if m else None

root = ET.parse(KML).getroot()
feats = []
for folder in root.iter("{http://www.opengis.net/kml/2.2}Folder"):
    nm = folder.find("k:name", NS)
    categoria = (nm.text or "").replace(".xlsx", "").strip().title() if nm is not None else "—"
    for pm in folder.findall("k:Placemark", NS):
        nombre = pm.findtext("k:name", default="", namespaces=NS).strip()
        coord = pm.findtext(".//k:coordinates", default="", namespaces=NS).strip()
        if not coord:
            continue
        lon, lat = (round(float(x), 5) for x in coord.split(",")[:2])
        desc = pm.findtext("k:description", default="", namespaces=NS)
        feats.append({"type": "Feature",
                      "properties": {"nombre": nombre, "categoria": categoria,
                                     "tipo": campo(desc, "TIPO"),
                                     "departamento": campo(desc, "DEPARTAMENTO"),
                                     "distrito": campo(desc, "DISTRITO")},
                      "geometry": {"type": "Point", "coordinates": [lon, lat]}})

out = os.path.join(OUT, "mspbs_salud.geojson")
json.dump({"type": "FeatureCollection",
           "metadata": {"fuente": "MSPBS / DIGIES, establecimientos de salud georreferenciados",
                        "url": "https://digies.mspbs.gov.py/establecimientos-de-salud-georeferenciados/",
                        "n": len(feats)},
           "features": feats}, open(out, "w", encoding="utf-8"), separators=(",", ":"))
from collections import Counter
print("establecimientos de salud:", len(feats))
for c, n in Counter(f["properties"]["categoria"] for f in feats).most_common():
    print(f"  {c}: {n}")
