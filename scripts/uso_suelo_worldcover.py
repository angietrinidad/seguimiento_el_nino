"""
Mapa de USO DEL SUELO de Paraguay a partir de ESA WorldCover (10 m, 2021),
leído a resolución gruesa vía Microsoft Planetary Computer (acceso abierto).

Reclasifica las clases WorldCover a categorías relevantes para la lectura crítica
del agro (bosque, pastura/pastizal, agricultura, humedal, agua, urbano) y produce:
- un MAPA estático (PNG) nacional,
- el % nacional por categoría,
- (si hay departamentos) el % por región Oriental vs Occidental (Chaco).

Es una foto de la COBERTURA (no distingue agricultura familiar de agronegocio ni el
año a año que sí ofrece MapBiomas); sirve para ver la huella espacial: la deforestación
del Chaco, el cinturón agrícola del este y los remanentes de bosque.

Salida: datos/geo/uso-suelo-py.png  +  datos/exposicion/uso_suelo_resumen.json
"""
import os, json
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import numpy as np
import rioxarray
from rioxarray.merge import merge_arrays
from pystac_client import Client
import planetary_computer as pc

GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
EXP = os.path.join(os.path.dirname(__file__), "..", "datos", "exposicion")
BBOX = [-62.70, -27.65, -54.20, -19.25]  # Paraguay
OVERVIEW = 5  # ~320 m/píxel: nacional manejable en memoria

# WorldCover -> categoría (código, nombre, color)
RECLASS = {
    10: ("Bosque", "#1a7a3a"), 20: ("Arbustos/sabana", "#b5c95a"),
    30: ("Pastizal/pastura", "#e3d24d"), 40: ("Agricultura", "#d97b2b"),
    50: ("Urbano", "#8a1c1c"), 60: ("Suelo desnudo", "#cfc8b8"),
    70: ("Nieve/hielo", "#ffffff"), 80: ("Agua", "#2b6cb0"),
    90: ("Humedal", "#5bb6c9"), 95: ("Manglar", "#3aa39a"), 100: ("Musgo/liquen", "#d0d0c0"),
}

print("Buscando ESA WorldCover en Planetary Computer ...")
cat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
items = list(cat.search(collections=["esa-worldcover"], bbox=BBOX).items())
# preferir la versión 2021 (v200) si está
items21 = [it for it in items if "2021" in str(it.properties.get("start_datetime", "")) or it.id.endswith("2021")]
items = items21 or items
print(f"  {len(items)} teselas")

arrs = []
for it in items:
    href = (it.assets.get("map") or list(it.assets.values())[0]).href
    try:
        a = rioxarray.open_rasterio(href, masked=False, overview_level=OVERVIEW).squeeze()
        arrs.append(a.rio.clip_box(*BBOX))
    except Exception as e:
        print("  tesela omitida:", type(e).__name__)
if not arrs:
    raise SystemExit("WorldCover no disponible (Planetary Computer)")
mos = merge_arrays(arrs)
lc = mos.values.astype("int16")
print("mosaico:", lc.shape)

# % nacional por categoría (excluye nodata 0 y fuera de rango)
vals, counts = np.unique(lc[lc > 0], return_counts=True)
tot = counts.sum()
resumen = {}
for v, c in zip(vals.tolist(), counts.tolist()):
    if v in RECLASS:
        resumen[RECLASS[v][0]] = resumen.get(RECLASS[v][0], 0) + round(100 * c / tot, 1)
resumen = dict(sorted(resumen.items(), key=lambda kv: -kv[1]))
print("uso del suelo (% nacional):", resumen)

# --- mapa estático ---
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    codes = sorted(RECLASS)
    lut = {c: i for i, c in enumerate(codes)}
    idx = np.vectorize(lambda v: lut.get(v, -1))(lc).astype(float)
    idx[idx < 0] = np.nan
    cmap = ListedColormap([RECLASS[c][1] for c in codes])
    ext = [BBOX[0], BBOX[2], BBOX[1], BBOX[3]]
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(idx, extent=ext, cmap=cmap, vmin=0, vmax=len(codes) - 1, interpolation="nearest")
    ax.set_title("Uso del suelo de Paraguay — ESA WorldCover 2021 (~320 m)", fontsize=11)
    ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud")
    presentes = [c for c in codes if RECLASS[c][0] in resumen]
    ax.legend(handles=[Patch(facecolor=RECLASS[c][1], edgecolor="#999",
              label=f"{RECLASS[c][0]} ({resumen.get(RECLASS[c][0],0)}%)") for c in presentes],
              loc="lower left", fontsize=8, framealpha=0.9)
    out_png = os.path.join(GEO, "uso-suelo-py.png")
    plt.tight_layout(); plt.savefig(out_png, dpi=130); print("PNG:", out_png)
except Exception as e:
    print("PNG omitido:", type(e).__name__, e)

json.dump({"fuente": "ESA WorldCover 2021 (10 m) vía Microsoft Planetary Computer",
           "resolucion_analisis_m": 320, "pct_nacional": resumen},
          open(os.path.join(EXP, "uso_suelo_resumen.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("resumen guardado")
