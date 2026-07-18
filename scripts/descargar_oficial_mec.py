"""
Descarga el directorio OFICIAL georreferenciado de establecimientos escolares del
MEC (datos.mec.gov.py) y le une los nombres de institución.

Endpoint (descubierto del mapa oficial): /app/mapa_establecimientos/datos
- tipo_consulta=11 -> TopoJSON: coordenadas + codigo_establecimiento
- tipo_consulta=12 -> JSON: instituciones (codigo_establecimiento -> nombre)
- tipo_consulta=13&establecimiento=COD -> matrícula por año (se consulta aparte,
  solo para los establecimientos expuestos, en procesar_exposicion.py).

Salida: datos/oficial/mec_escuelas_oficiales.geojson (punto = establecimiento,
con la lista de instituciones y sus nombres). Período 2014 (último del portal).
"""
import os, json, urllib.request

BASE = "https://datos.mec.gov.py/app/mapa_establecimientos/datos"
PERIODO = "2014"
OUT = os.path.join(os.path.dirname(__file__), "..", "datos", "oficial")
os.makedirs(OUT, exist_ok=True)


def bajar(tipo):
    url = f"{BASE}?tipo_consulta={tipo}&periodo={PERIODO}"
    raw = urllib.request.urlopen(url, timeout=90).read()
    try:
        return json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return json.loads(raw.decode("latin-1"))


# --- 11: coordenadas por establecimiento ---
topo = bajar("11")
tr = topo["transform"]; sc, tl = tr["scale"], tr["translate"]
coords = {}
for g in list(topo["objects"].values())[0]["geometries"]:
    c = g["coordinates"]
    coords[g["properties"]["codigo_establecimiento"]] = [
        round(c[0] * sc[0] + tl[0], 5), round(c[1] * sc[1] + tl[1], 5)]
print("establecimientos con coords:", len(coords))

# --- 12: instituciones (nombres) por establecimiento ---
insts = bajar("12")
por_est = {}
for r in insts:
    ce = r.get("codigo_establecimiento")
    if not ce:
        continue
    por_est.setdefault(ce, []).append({
        "codigo_institucion": r.get("codigo_institucion"),
        "nombre": r.get("nombre_institucion"),
        "departamento": r.get("nombre_departamento"),
        "distrito": r.get("nombre_distrito"),
        "barrio": r.get("nombre_barrio_localidad")})
print("establecimientos con instituciones:", len(por_est))

# --- unir ---
feats = []
for ce, xy in coords.items():
    inst = por_est.get(ce, [])
    nombres = [i["nombre"] for i in inst if i["nombre"]]
    meta = inst[0] if inst else {}
    feats.append({"type": "Feature",
                  "properties": {"codigo_establecimiento": ce,
                                 "nombre": " / ".join(nombres) if nombres else f"establecimiento {ce}",
                                 "n_instituciones": len(inst),
                                 "departamento": meta.get("departamento"),
                                 "distrito": meta.get("distrito"),
                                 "barrio": meta.get("barrio")},
                  "geometry": {"type": "Point", "coordinates": xy}})
out = os.path.join(OUT, "mec_escuelas_oficiales.geojson")
json.dump({"type": "FeatureCollection",
           "metadata": {"fuente": "MEC (datos.mec.gov.py), directorio oficial georreferenciado",
                        "periodo": PERIODO, "n": len(feats)},
           "features": feats}, open(out, "w", encoding="utf-8"), separators=(",", ":"))
con_nombre = sum(1 for f in feats if not f["properties"]["nombre"].startswith("establecimiento "))
print(f"guardado: {len(feats)} establecimientos ({con_nombre} con nombre) | {round(os.path.getsize(out)/1024)} KB")
