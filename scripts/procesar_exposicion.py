"""
Cruza población, servicios de salud y centros educativos con los departamentos y
con las huellas de inundación de Asunción, para el mapa de exposición.

Fuentes (todas abiertas):
- Población por departamento 2023: COD-PS (UNFPA/DGEEC), CC BY-IGO.
- Salud: healthsites.io / OSM (ODbL).
- Educación: HOT / OSM (ODbL).
- Departamentos: geoBoundaries (CC BY).
- Huellas de inundación: derivadas de Sentinel-1 (este repositorio).

Salidas:
- datos/geo/departamentos-exposicion.geojson  (pop, niñez, mayores, n_salud, n_escuelas)
- datos/geo/salud-puntos.geojson               (hospitales/clínicas, puntos)
- datos/geo/escuelas-puntos.geojson            (centros educativos, puntos)
- datos/geo/expuestos-inundacion.geojson       (salud/escuelas dentro de huellas Asunción)
- datos/exposicion/resumen.json                (tablero de cifras)
"""
import os, csv, json, unicodedata
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union
from shapely.prepared import prep

GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
EXP = os.path.join(os.path.dirname(__file__), "..", "datos", "exposicion")
PRIORITARIOS = {"CENTRAL", "CONCEPCION", "SAN PEDRO", "PRESIDENTE HAYES",
                "ÑEEMBUCU", "MISIONES", "ITAPUA", "ALTO PARANA"}

def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()

def puntos(path, amenities):
    """Devuelve lista de (lon, lat, nombre, tipo) filtrando por amenity."""
    out = []
    for f in json.load(open(path, encoding="utf-8"))["features"]:
        p = f["properties"]
        tipo = p.get("amenity") or p.get("healthcare")
        if tipo not in amenities:
            continue
        g = shape(f["geometry"])
        c = g if g.geom_type == "Point" else g.centroid
        out.append((round(c.x, 5), round(c.y, 5),
                    p.get("name") or p.get("name_es") or "(sin nombre)", tipo))
    return out

# --- Población por departamento (0-14 niñez, 65+ mayores) ---
pop = {}
for r in csv.DictReader(open(os.path.join(EXP, "poblacion_adm1_2023.csv"), encoding="utf-8-sig")):
    n = norm(r["ADM1_NAME"])
    ninez = sum(int(r[c]) for c in ["T_00_04", "T_05_09", "T_10_14"])
    may = sum(int(r[c]) for c in ["T_65_69", "T_70_74", "T_75_79", "T_80Plus"])
    pop[n] = {"total": int(r["T_TL"]), "ninez": ninez, "mayores": may}

# --- Puntos de salud y educación ---
salud = puntos(os.path.join(GEO, "health_raw.geojson"), {"hospital", "clinic", "doctors"})
escuelas = puntos(os.path.join(GEO, "education_facilities.geojson"),
                  {"school", "kindergarten", "college", "university"})
print(f"salud: {len(salud)} | escuelas: {len(escuelas)}")

# --- Departamentos con conteos ---
deps = json.load(open(os.path.join(GEO, "departamentos-py.geojson"), encoding="utf-8"))
prep_deps = [(f, prep(shape(f["geometry"]))) for f in deps["features"]]

def depto_de(lon, lat):
    pt = Point(lon, lat)
    for f, pg in prep_deps:
        if pg.contains(pt):
            return norm(f["properties"]["shapeName"])
    return None

cnt_salud, cnt_esc = {}, {}
for lon, lat, *_ in salud:
    d = depto_de(lon, lat)
    if d: cnt_salud[d] = cnt_salud.get(d, 0) + 1
for lon, lat, *_ in escuelas:
    d = depto_de(lon, lat)
    if d: cnt_esc[d] = cnt_esc.get(d, 0) + 1

for f in deps["features"]:
    n = norm(f["properties"]["shapeName"])
    pr = f["properties"]
    pr["pop_total"] = pop.get(n, {}).get("total")
    pr["pop_ninez"] = pop.get(n, {}).get("ninez")
    pr["pop_mayores"] = pop.get(n, {}).get("mayores")
    pr["n_salud"] = cnt_salud.get(n, 0)
    pr["n_escuelas"] = cnt_esc.get(n, 0)
    pr["prioritario"] = n in PRIORITARIOS

# --- Zonas de riesgo de inundación (multi-zona) ---
# Cada zona = unión de huellas Sentinel-1 + buffer ~550 m (barrios adyacentes).
BUFFER_DEG = 0.005
ZONAS = [
    {"id": "asuncion", "nombre": "Asunción y área metropolitana",
     "huellas": ["inundacion-2015-16-s1.geojson", "inundacion-2018-19-s1.geojson",
                 "inundacion-2023-24-s1.geojson"]},
    {"id": "neembucu", "nombre": "Pilar / Ñeembucú",
     "huellas": ["zona-anegamiento-neembucu-s1.geojson"]},
]

def guardar(obj, path):
    json.dump(obj, open(path, "w", encoding="utf-8"), separators=(",", ":"))

exp_feats, zona_feats, resumen_zonas = [], [], {}
for z in ZONAS:
    geoms = []
    for fn in z["huellas"]:
        ruta = os.path.join(GEO, fn)
        if not os.path.exists(ruta):
            continue
        for f in json.load(open(ruta, encoding="utf-8"))["features"]:
            g = shape(f["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            geoms.append(g)
    if not geoms:
        continue
    zona = unary_union(geoms).buffer(BUFFER_DEG)
    pz = prep(zona)
    ns = ne = 0
    for lon, lat, nom, tipo in salud:
        if pz.contains(Point(lon, lat)):
            ns += 1
            exp_feats.append({"type": "Feature",
                              "properties": {"clase": "salud", "tipo": tipo, "nombre": nom, "zona": z["nombre"]},
                              "geometry": {"type": "Point", "coordinates": [lon, lat]}})
    for lon, lat, nom, tipo in escuelas:
        if pz.contains(Point(lon, lat)):
            ne += 1
            exp_feats.append({"type": "Feature",
                              "properties": {"clase": "educacion", "tipo": tipo, "nombre": nom, "zona": z["nombre"]},
                              "geometry": {"type": "Point", "coordinates": [lon, lat]}})
    resumen_zonas[z["id"]] = {"nombre": z["nombre"], "salud_expuestos": ns, "escuelas_expuestos": ne}
    zona_feats.append({"type": "Feature", "properties": {"zona": z["nombre"]},
                       "geometry": mapping(zona.simplify(0.0003))})
    print(f"{z['nombre']}: salud {ns} | escuelas {ne}")

# --- Guardar capas ---
guardar(deps, os.path.join(GEO, "departamentos-exposicion.geojson"))
guardar({"type": "FeatureCollection",
         "features": [{"type": "Feature", "properties": {"nombre": n, "tipo": t},
                       "geometry": {"type": "Point", "coordinates": [x, y]}} for x, y, n, t in salud]},
        os.path.join(GEO, "salud-puntos.geojson"))
guardar({"type": "FeatureCollection",
         "features": [{"type": "Feature", "properties": {"nombre": n, "tipo": t},
                       "geometry": {"type": "Point", "coordinates": [x, y]}} for x, y, n, t in escuelas]},
        os.path.join(GEO, "escuelas-puntos.geojson"))
guardar({"type": "FeatureCollection", "features": exp_feats},
        os.path.join(GEO, "expuestos-inundacion.geojson"))
guardar({"type": "FeatureCollection", "features": zona_feats},
        os.path.join(GEO, "zona-riesgo-inundacion.geojson"))

# --- Tablero ---
prio = [n for n in PRIORITARIOS]
resumen = {
    "nacional": {"poblacion": sum(v["total"] for v in pop.values()),
                 "salud": len(salud), "escuelas": len(escuelas)},
    "departamentos_prioritarios": {
        "poblacion": sum(pop.get(n, {}).get("total", 0) for n in prio),
        "ninez": sum(pop.get(n, {}).get("ninez", 0) for n in prio),
        "mayores": sum(pop.get(n, {}).get("mayores", 0) for n in prio),
        "salud": sum(cnt_salud.get(n, 0) for n in prio),
        "escuelas": sum(cnt_esc.get(n, 0) for n in prio)},
    "zonas_riesgo": resumen_zonas,
}
guardar(resumen, os.path.join(EXP, "resumen.json"))
print(json.dumps(resumen["zonas_riesgo"], indent=2, ensure_ascii=False))
