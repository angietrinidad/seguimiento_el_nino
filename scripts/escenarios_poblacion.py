"""
Población expuesta por ESCENARIO de riesgo (Gran Asunción, 2026-27).

Reutiliza exactamente la metodología del modelo de exposición
(scripts/procesar_exposicion.py): cruza la malla de población Kontur (H3 ~400 m)
con la huella de inundación de cada episodio (derivada por nosotros de Sentinel-1,
preliminar) más un buffer de ~550 m para barrios adyacentes, y desagrega por edad
aplicando la estructura etaria departamental (COD-PS 2023, 0-14 niñez / 65+ mayores).

Escenarios:
- severo   ≈ crecida de 2019 (río 7,57 m)  → huella inundacion-2018-19-s1
- extremo  ≈ El Niño 2015-16 (río 7,84 m)  → huella inundacion-2015-16-s1
- (el escenario 'esperado'/pluvial no es una huella fluvial: su población proviene
   del corredor de susceptibilidad pluvial DEM, ya calculada en pluvial_resumen.json)

Fuentes:
- Población y estructura etaria: COD-PS 2023 (UNFPA/DGEEC), CC BY-IGO.
- Malla de población: Kontur Population (H3), CC BY.
- Huellas de inundación: derivadas de Sentinel-1 (este repositorio, preliminares).
- Salud: MSPBS/DIGIES. Educación: MEC (directorio oficial georreferenciado).

Salida: datos/exposicion/escenarios_poblacion.json
"""
import os, csv, json, unicodedata
import geopandas as gpd
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

BASE = os.path.dirname(__file__)
GEO = os.path.join(BASE, "..", "datos", "geo")
EXP = os.path.join(BASE, "..", "datos", "exposicion")
OFI = os.path.join(BASE, "..", "datos", "oficial")
BUFFER_DEG = 0.005  # ~550 m, idéntico a procesar_exposicion.py

def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()

# --- estructura etaria por departamento (COD-PS 2023) ---
pop = {}
for r in csv.DictReader(open(os.path.join(EXP, "poblacion_adm1_2023.csv"), encoding="utf-8-sig")):
    n = norm(r["ADM1_NAME"])
    ninez = sum(int(r[c]) for c in ["T_00_04", "T_05_09", "T_10_14"])
    may = sum(int(r[c]) for c in ["T_65_69", "T_70_74", "T_75_79", "T_80Plus"])
    tot = int(r["T_TL"])
    pop[n] = {"total": tot, "ninez": ninez, "mayores": may}

# --- capas base ---
k = gpd.read_file(os.path.join(OFI, "kontur_py.gpkg"))
cent = gpd.GeoDataFrame({"population": k["population"].values},
                        geometry=k.geometry.centroid.to_crs(4326).values, crs=4326)
deps_g = gpd.read_file(os.path.join(GEO, "departamentos-py.geojson"))[["shapeName", "geometry"]]
cent_dep = gpd.sjoin(cent, deps_g, predicate="within").drop(columns="index_right")

def cargar_puntos(path, campo_nombre):
    out = []
    for f in json.load(open(path, encoding="utf-8"))["features"]:
        lon, lat = f["geometry"]["coordinates"]
        out.append((lon, lat, f["properties"].get(campo_nombre)))
    return out
salud = cargar_puntos(os.path.join(OFI, "mspbs_salud.geojson"), "nombre")
escuelas = cargar_puntos(os.path.join(OFI, "mec_escuelas_oficiales.geojson"), "nombre")

def huella_zona(archivos):
    geoms = []
    for fn in archivos:
        ruta = os.path.join(GEO, fn)
        if not os.path.exists(ruta):
            continue
        for f in json.load(open(ruta, encoding="utf-8"))["features"]:
            g = shape(f["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            geoms.append(g)
    return unary_union(geoms).buffer(BUFFER_DEG)

def poblacion_en(zona):
    """Población total + niñez + mayores dentro de la zona, ponderando por la
    estructura etaria del departamento de cada hexágono."""
    risk = gpd.GeoDataFrame(geometry=[zona], crs=4326)
    inr = gpd.sjoin(cent_dep, risk, predicate="within").drop(columns="index_right")
    tot = ninez = may = 0
    for nm, val in inr.groupby("shapeName")["population"].sum().items():
        d = pop.get(norm(nm))
        val = float(val)
        tot += val
        if d and d["total"]:
            ninez += val * d["ninez"] / d["total"]
            may += val * d["mayores"] / d["total"]
    pz = prep(zona)
    ns = sum(1 for lon, lat, _ in salud if pz.contains(Point(lon, lat)))
    ne = sum(1 for lon, lat, _ in escuelas if pz.contains(Point(lon, lat)))
    return {"poblacion": int(round(tot)), "ninez": int(round(ninez)),
            "mayores": int(round(may)), "salud": ns, "escuelas": ne}

ESCENARIOS = {
    "severo":  {"huellas": ["inundacion-2018-19-s1.geojson"],
                "detonante": "río ~7,57 m (crecida de 2019)"},
    "extremo": {"huellas": ["inundacion-2015-16-s1.geojson"],
                "detonante": "río ~7,84 m (El Niño 2015-16)"},
}
salida = {}
for cid, meta in ESCENARIOS.items():
    z = huella_zona(meta["huellas"])
    r = poblacion_en(z)
    r["detonante"] = meta["detonante"]
    salida[cid] = r
    print(cid, r)

# escenario pluvial (esperado): del corredor de susceptibilidad DEM ya calculado
pluv = json.load(open(os.path.join(EXP, "pluvial_resumen.json"), encoding="utf-8"))
salida["esperado_pluvial"] = {
    "poblacion": pluv.get("poblacion"), "escuelas": pluv.get("escuelas"),
    "salud": pluv.get("salud"),
    "detonante": "temporales intensos (corredor de susceptibilidad pluvial DEM, buffer 100 m)",
    "nota": "diffuse: puntos bajos de la ciudad, no una huella fluvial contigua"}
print("esperado_pluvial", salida["esperado_pluvial"])

# validación: la unión de las tres huellas debe reproducir ~en_riesgo (59.695)
union3 = huella_zona(["inundacion-2015-16-s1.geojson", "inundacion-2018-19-s1.geojson",
                      "inundacion-2023-24-s1.geojson"])
salida["_validacion_union_huellas"] = poblacion_en(union3)["poblacion"]
print("validación unión 3 huellas (debe ≈ 59.695):", salida["_validacion_union_huellas"])

salida["_fuentes"] = ("Kontur Population (H3) × huellas Sentinel-1 (preliminares, este repo) "
                      "+ buffer 550 m; estructura etaria COD-PS 2023; salud MSPBS, educación MEC.")
json.dump(salida, open(os.path.join(EXP, "escenarios_poblacion.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print("OK -> datos/exposicion/escenarios_poblacion.json")
