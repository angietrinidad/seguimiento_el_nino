"""
Exposición a la susceptibilidad pluvial ALTA en Asunción metro:
población (Kontur H3), escuelas (MEC) y servicios de salud (MSPBS) cuyo punto
cae dentro de la zona pluvial alta modelada (analisis_pluvial_dem.py).

Salida: datos/exposicion/pluvial_resumen.json
"""
import os, json
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
OFI = os.path.join(os.path.dirname(__file__), "..", "datos", "oficial")
EXP = os.path.join(os.path.dirname(__file__), "..", "datos", "exposicion")

d = json.load(open(os.path.join(GEO, "susceptibilidad-pluvial-asuncion.geojson"), encoding="utf-8"))
alta0 = unary_union([shape(f["geometry"]) for f in d["features"] if f["properties"]["clase"] == "alta"])
# El corredor de drenaje del DEM es angosto (1-2 celdas); la inundación pluvial se
# extiende lateralmente. Se cuenta la exposición en un margen anegable de ~100 m.
BUFFER = 0.0009  # ~100 m
alta = alta0.buffer(BUFFER)
pa = prep(alta)
km2 = d["metadata"]["km2"]

# escuelas MEC
esc = json.load(open(os.path.join(OFI, "mec_escuelas_oficiales.geojson"), encoding="utf-8"))["features"]
n_esc = sum(1 for f in esc if pa.contains(Point(*f["geometry"]["coordinates"])))

# salud MSPBS
sal = json.load(open(os.path.join(OFI, "mspbs_salud.geojson"), encoding="utf-8"))["features"]
def pt(f):
    c = f["geometry"]["coordinates"]
    return Point(c[0], c[1])
n_sal = sum(1 for f in sal if f["geometry"]["type"] == "Point" and pa.contains(pt(f)))

# población Kontur
pop = None
try:
    import geopandas as gpd
    k = gpd.read_file(os.path.join(OFI, "kontur_py.gpkg"))
    cent = gpd.GeoDataFrame({"population": k["population"].values},
                            geometry=k.geometry.centroid.to_crs(4326).values, crs=4326)
    risk = gpd.GeoDataFrame(geometry=[alta], crs=4326)
    inr = gpd.sjoin(cent, risk, predicate="within")
    pop = int(round(inr["population"].sum()))
except Exception as e:
    print("pop no disponible:", e)

import pyproj
from shapely.ops import transform as shp_transform
to_utm = pyproj.Transformer.from_crs(4326, "EPSG:32721", always_xy=True).transform
km2_buf = round(shp_transform(to_utm, alta).area / 1e6, 1)
res = {"km2_alta": km2.get("alta"), "km2_media": km2.get("media"),
       "km2_corredor_100m": km2_buf, "buffer_m": 100,
       "escuelas": n_esc, "salud": n_sal, "poblacion": pop}
json.dump(res, open(os.path.join(EXP, "pluvial_resumen.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(res)
