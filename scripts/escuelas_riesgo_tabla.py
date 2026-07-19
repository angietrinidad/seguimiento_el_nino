"""
Genera la tabla de ESCUELAS EN RIESGO de inundación para exportar a Excel.

Por cada establecimiento educativo (MEC) dentro de una zona de riesgo:
- ubicación (departamento, distrito, barrio, lat, lon)
- instituciones que alberga y su matrícula (MEC, último año disponible)
- tipo de gestión (oficial / privada / privada subvencionada) — se infiere del
  nombre oficial de la institución (marcas "PRIV." / "PRIV.SUBV.")
- zona de riesgo y a qué nivel del río se inundó (observado por episodio)

Salida: datos/exposicion/escuelas_riesgo.json (insumo para el Excel).
"""
import os, json, urllib.request, time
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
OFI = os.path.join(os.path.dirname(__file__), "..", "datos", "oficial")
EXP = os.path.join(os.path.dirname(__file__), "..", "datos", "exposicion")


def cargar_union(fn, buffer=0.005):
    gs = []
    for f in json.load(open(os.path.join(GEO, fn), encoding="utf-8"))["features"]:
        g = shape(f["geometry"]); gs.append(g if g.is_valid else g.buffer(0))
    return unary_union(gs).buffer(buffer) if gs else None


# Zonas (nombre -> unión de huellas + buffer 0.005). Orden específica-primero para
# que las zonas chicas no queden absorbidas por la metropolitana de Asunción.
def zona_union(fns):
    gs = []
    for fn in fns:
        for f in json.load(open(os.path.join(GEO, fn), encoding="utf-8"))["features"]:
            g = shape(f["geometry"]); gs.append(g if g.is_valid else g.buffer(0))
    return unary_union(gs).buffer(0.005)

ZONAS = [
    ("Villa Hayes", ["anegamiento-villahayes-s1.geojson"]),
    ("Alberdi / bajo Ñeembucú", ["anegamiento-alberdi-s1.geojson"]),
    ("Pilar / Ñeembucú", ["zona-anegamiento-neembucu-s1.geojson"]),
    ("Asunción y área metropolitana", ["inundacion-2015-16-s1.geojson",
        "inundacion-2018-19-s1.geojson", "inundacion-2023-24-s1.geojson"]),
]
zonas_geom = [(n, prep(zona_union(fns))) for n, fns in ZONAS]

# Huellas por episodio en Asunción (para el nivel del río observado), SIN buffer
def huella_ep(fn):
    gs = [shape(f["geometry"]).buffer(0) for f in
          json.load(open(os.path.join(GEO, fn), encoding="utf-8"))["features"]]
    return prep(unary_union(gs).buffer(0.005))
h_2016 = huella_ep("inundacion-2015-16-s1.geojson")
h_2019 = huella_ep("inundacion-2018-19-s1.geojson")

_cache = {}
def instituciones(cod):
    if cod in _cache:
        return _cache[cod]
    res = {"instituciones": [], "matricula": None, "anio": None}
    u = ("https://datos.mec.gov.py/app/mapa_establecimientos/datos"
         f"?tipo_consulta=13&periodo=2014&establecimiento={cod}")
    for intento in range(3):  # reintenta ante fallos de red transitorios
        try:
            raw = urllib.request.urlopen(u, timeout=30).read()
            try:
                data = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError:
                data = json.loads(raw.decode("latin-1"))
            # Método consistente con procesar_exposicion: se toma el ÚNICO último
            # año del establecimiento y se suman las instituciones de ese año.
            por_anio = {}
            for inst in data:
                res["instituciones"].append(inst.get("nombre_institucion", ""))
                for y, v in (inst.get("cantidad_matriculados") or {}).items():
                    if v and v not in ("--", ""):
                        por_anio[y] = por_anio.get(y, 0) + int(v)
            if por_anio:
                a = max(por_anio)
                res["matricula"], res["anio"] = por_anio[a], a
            break
        except Exception:
            time.sleep(1.5 * (intento + 1))
    _cache[cod] = res
    return res


def gestion(nombre):
    n = (nombre or "").upper()
    if "SUBV" in n:
        return "Privada subvencionada"
    if "PRIV" in n:
        return "Privada"
    return "Oficial (pública)"


feats = json.load(open(os.path.join(OFI, "mec_escuelas_oficiales.geojson"), encoding="utf-8"))["features"]
filas = []
for f in feats:
    lon, lat = f["geometry"]["coordinates"]
    pt = Point(lon, lat)
    zona = next((n for n, pz in zonas_geom if pz.contains(pt)), None)
    if not zona:
        continue
    p = f["properties"]
    insts = instituciones(p["codigo_establecimiento"])
    total_mat = insts["matricula"]
    anio = insts["anio"]
    gests = sorted({gestion(n) for n in insts["instituciones"]}) or ["s/d"]
    # nivel del río observado (solo Asunción, por huella de episodio)
    if zona.startswith("Asunción"):
        if h_2019.contains(pt):
            nivel = "≈ 7,57 m (se inundó en 2018-19)"
        elif h_2016.contains(pt):
            nivel = "≈ 7,88 m (se inundó en 2015-16)"
        else:
            nivel = "≥ 7,5 m (zona de riesgo)"
    else:
        nivel = "zona de anegamiento recurrente (estación local)"
    filas.append({
        "institucion": p.get("nombre", ""),
        "departamento": p.get("departamento", ""), "distrito": p.get("distrito", ""),
        "barrio": p.get("barrio", ""), "lat": round(lat, 5), "lon": round(lon, 5),
        "matricula": total_mat, "anio_matricula": anio,
        "gestion": " / ".join(gests), "zona": zona, "nivel_rio": nivel,
        "n_instituciones": len(insts["instituciones"])})

filas.sort(key=lambda r: (r["zona"], -(r["matricula"] or 0)))
json.dump(filas, open(os.path.join(EXP, "escuelas_riesgo.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"escuelas en riesgo: {len(filas)}")
tot = sum(r["matricula"] or 0 for r in filas)
print(f"matrícula total: {tot:,}")
from collections import Counter
print("por gestión:", dict(Counter(r["gestion"] for r in filas)))
print("por zona:", dict(Counter(r["zona"] for r in filas)))
