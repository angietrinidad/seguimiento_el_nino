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
import os, csv, json, unicodedata, time
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union
from shapely.prepared import prep

GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
EXP = os.path.join(os.path.dirname(__file__), "..", "datos", "exposicion")
OFI = os.path.join(os.path.dirname(__file__), "..", "datos", "oficial")
PRIORITARIOS = {"CENTRAL", "CONCEPCION", "SAN PEDRO", "PRESIDENTE HAYES",
                "ÑEEMBUCU", "MISIONES", "ITAPUA", "ALTO PARANA"}

def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()

def puntos(path, clase, amenities):
    """Lista de dicts (lon, lat, nombre, tipo, detalle) filtrando por amenity.
    OSM NO trae capacidad/matrícula (campo vacío), así que no se incluye.
    A los establecimientos sin nombre se les arma una etiqueta por tipo + ciudad."""
    out = []
    for f in json.load(open(path, encoding="utf-8"))["features"]:
        p = f["properties"]
        tipo = p.get("amenity") or p.get("healthcare")
        if tipo not in amenities:
            continue
        g = shape(f["geometry"])
        c = g if g.geom_type == "Point" else g.centroid
        nombre = p.get("name") or p.get("name_es") or p.get("name_gn")
        ciudad = p.get("addr_city") or p.get("adm2_name")
        if clase == "salud":
            detalle = {"ciudad": ciudad, "operador": p.get("operator"),
                       "especialidad": p.get("speciality"),
                       "emergencia": "sí" if p.get("emergency") in ("yes", "emergency") else None}
        else:
            detalle = {"ciudad": ciudad, "operador": p.get("operator_type")}
        if not nombre:
            nombre = f"{tipo} sin nombre" + (f" ({ciudad})" if ciudad else "")
        detalle = {k: v for k, v in detalle.items() if v}
        out.append({"lon": round(c.x, 5), "lat": round(c.y, 5),
                    "nombre": nombre, "tipo": tipo, "detalle": detalle})
    return out

# --- Población por departamento (0-14 niñez, 65+ mayores) ---
pop = {}
for r in csv.DictReader(open(os.path.join(EXP, "poblacion_adm1_2023.csv"), encoding="utf-8-sig")):
    n = norm(r["ADM1_NAME"])
    ninez = sum(int(r[c]) for c in ["T_00_04", "T_05_09", "T_10_14"])
    may = sum(int(r[c]) for c in ["T_65_69", "T_70_74", "T_75_79", "T_80Plus"])
    pop[n] = {"total": int(r["T_TL"]), "ninez": ninez, "mayores": may}

# --- Salud: registro OFICIAL del MSPBS (DIGIES) ---
def cargar_salud_oficial(path):
    out = []
    for f in json.load(open(path, encoding="utf-8"))["features"]:
        p = f["properties"]; lon, lat = f["geometry"]["coordinates"]
        detalle = {k: v for k, v in {"categoria": p.get("categoria"), "subtipo": p.get("tipo"),
                   "distrito": p.get("distrito")}.items() if v}
        out.append({"lon": lon, "lat": lat, "nombre": p.get("nombre"),
                    "tipo": p.get("categoria") or "establecimiento de salud", "detalle": detalle})
    return out
salud = cargar_salud_oficial(os.path.join(OFI, "mspbs_salud.geojson"))

# --- Educación: directorio OFICIAL del MEC (georreferenciado, con nombre) ---
def cargar_escuelas_oficiales(path):
    out = []
    for f in json.load(open(path, encoding="utf-8"))["features"]:
        p = f["properties"]; lon, lat = f["geometry"]["coordinates"]
        detalle = {k: v for k, v in {"distrito": p.get("distrito"), "barrio": p.get("barrio"),
                   "instituciones": p.get("n_instituciones")}.items() if v}
        out.append({"lon": lon, "lat": lat, "nombre": p.get("nombre"),
                    "tipo": "establecimiento educativo", "codigo": p.get("codigo_establecimiento"),
                    "detalle": detalle})
    return out
escuelas = cargar_escuelas_oficiales(os.path.join(OFI, "mec_escuelas_oficiales.geojson"))
print(f"salud (MSPBS oficial): {len(salud)} | escuelas (MEC oficial): {len(escuelas)}")

# Matrícula oficial (tc=13) — solo para establecimientos expuestos; con caché.
import urllib.request
_mat_cache = {}
def matricula(codigo):
    if codigo in _mat_cache:
        return _mat_cache[codigo]
    res = (None, None)
    url = ("https://datos.mec.gov.py/app/mapa_establecimientos/datos"
           f"?tipo_consulta=13&periodo=2014&establecimiento={codigo}")
    for intento in range(3):  # reintenta ante fallos de red transitorios
        try:
            raw = urllib.request.urlopen(url, timeout=30).read()
            try:
                data = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError:
                data = json.loads(raw.decode("latin-1"))
            por_anio = {}
            for inst in data:
                for y, v in (inst.get("cantidad_matriculados") or {}).items():
                    if v and v not in ("--", ""):
                        por_anio[y] = por_anio.get(y, 0) + int(v)
            if por_anio:
                a = max(por_anio); res = (por_anio[a], a)
            break
        except Exception:
            time.sleep(1.5 * (intento + 1))
    _mat_cache[codigo] = res
    return res

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
for r in salud:
    d = depto_de(r["lon"], r["lat"])
    if d: cnt_salud[d] = cnt_salud.get(d, 0) + 1
for r in escuelas:
    d = depto_de(r["lon"], r["lat"])
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
# Orden específica-primero: las zonas locales (Villa Hayes) reclaman sus
# establecimientos antes que la metropolitana de Asunción, con la que se solapan.
ZONAS = [
    {"id": "villahayes", "nombre": "Villa Hayes", "huellas": ["anegamiento-villahayes-s1.geojson"]},
    {"id": "fuerteolimpo", "nombre": "Fuerte Olimpo", "huellas": ["anegamiento-fuerteolimpo-s1.geojson"]},
    {"id": "alberdi", "nombre": "Alberdi / bajo Ñeembucú", "huellas": ["anegamiento-alberdi-s1.geojson"]},
    {"id": "neembucu", "nombre": "Pilar / Ñeembucú",
     "huellas": ["zona-anegamiento-neembucu-s1.geojson"]},
    {"id": "asuncion", "nombre": "Asunción y área metropolitana",
     "huellas": ["inundacion-2015-16-s1.geojson", "inundacion-2018-19-s1.geojson",
                 "inundacion-2023-24-s1.geojson"]},
]

def guardar(obj, path):
    json.dump(obj, open(path, "w", encoding="utf-8"), separators=(",", ":"))

exp_feats, zona_feats, resumen_zonas = [], [], {}
asignados = set()  # (lon,lat) ya contados: evita doble conteo en solapamientos
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
    for clase, lista in (("salud", salud), ("educacion", escuelas)):
        for r in lista:
            clave = (r["lon"], r["lat"])
            if clave in asignados:
                continue
            if pz.contains(Point(r["lon"], r["lat"])):
                asignados.add(clave)
                if clase == "salud": ns += 1
                else: ne += 1
                props = {"clase": clase, "tipo": r["tipo"], "nombre": r["nombre"], "zona": z["nombre"]}
                props.update(r["detalle"])
                if clase == "educacion" and r.get("codigo"):
                    tot, anio = matricula(r["codigo"])
                    if tot is not None:
                        props["matricula"] = tot; props["matricula_anio"] = anio
                exp_feats.append({"type": "Feature", "properties": props,
                                  "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]}})
    resumen_zonas[z["id"]] = {"nombre": z["nombre"], "salud_expuestos": ns, "escuelas_expuestos": ne}
    zona_feats.append({"type": "Feature", "properties": {"zona": z["nombre"]},
                       "geometry": mapping(zona.simplify(0.0003))})
    print(f"{z['nombre']}: salud {ns} | escuelas {ne}")

# --- EN RIESGO por departamento (población Kontur + establecimientos) ---
from collections import Counter
zona_union = unary_union([shape(zf["geometry"]) for zf in zona_feats])
pop_riesgo = {}
try:
    import geopandas as gpd
    k = gpd.read_file(os.path.join(OFI, "kontur_py.gpkg"))          # H3 ~400 m, EPSG:3857
    cent = gpd.GeoDataFrame({"population": k["population"].values},
                            geometry=k.geometry.centroid.to_crs(4326).values, crs=4326)
    risk = gpd.GeoDataFrame(geometry=[zona_union], crs=4326)
    deps_g = gpd.read_file(os.path.join(GEO, "departamentos-py.geojson"))[["shapeName", "geometry"]]
    inr = gpd.sjoin(cent, risk, predicate="within").drop(columns="index_right")
    inr = gpd.sjoin(inr, deps_g, predicate="within")
    for nm, val in inr.groupby("shapeName")["population"].sum().items():
        pop_riesgo[norm(nm)] = int(round(val))
    print("población en riesgo total:", sum(pop_riesgo.values()))
except Exception as e:
    print("pop_riesgo no disponible:", e)

sr, er, mr = Counter(), Counter(), Counter()
for f in exp_feats:
    lon, lat = f["geometry"]["coordinates"]; dd = depto_de(lon, lat)
    if not dd:
        continue
    if f["properties"]["clase"] == "salud":
        sr[dd] += 1
    else:
        er[dd] += 1; mr[dd] += f["properties"].get("matricula") or 0

for f in deps["features"]:
    n = norm(f["properties"]["shapeName"])
    f["properties"]["pop_riesgo"] = pop_riesgo.get(n, 0)
    f["properties"]["salud_riesgo"] = sr.get(n, 0)
    f["properties"]["escuelas_riesgo"] = er.get(n, 0)
    f["properties"]["matricula_riesgo"] = mr.get(n, 0)

# --- Guardar capas ---
def pts_fc(lista):
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature",
                          "properties": {"nombre": r["nombre"], "tipo": r["tipo"], **r["detalle"]},
                          "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]}} for r in lista]}

guardar(deps, os.path.join(GEO, "departamentos-exposicion.geojson"))
guardar(pts_fc(salud), os.path.join(GEO, "salud-puntos.geojson"))
guardar(pts_fc(escuelas), os.path.join(GEO, "escuelas-puntos.geojson"))
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
    "en_riesgo": {
        "poblacion": sum(pop_riesgo.values()),
        "salud": sum(sr.values()), "escuelas": sum(er.values()),
        "matricula": sum(mr.values())},
    "zonas_riesgo": resumen_zonas,
}
guardar(resumen, os.path.join(EXP, "resumen.json"))
print(json.dumps(resumen["zonas_riesgo"], indent=2, ensure_ascii=False))
