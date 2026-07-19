"""
Susceptibilidad a inundación PLUVIAL (por lluvia y drenaje insuficiente) en el
área urbana de Asunción, derivada de la topografía (Copernicus DEM GLO-30).

A diferencia de la inundación FLUVIAL (desborde del río, mapeada con Sentinel-1),
la pluvial ocurre donde el agua de lluvia se acumula por el relieve y la falta de
drenaje. Este análisis NO observa una inundación: MODELA dónde el terreno favorece
el encharcamiento y la concentración del escurrimiento. Es una capa de
SUSCEPTIBILIDAD (proxy topográfico), no un evento observado.

Método:
1. DEM Copernicus GLO-30 (30 m) sobre Asunción y metro interior.
2. Relleno de depresiones (algoritmo priority-flood): profundidad de depresión =
   DEM_rellenado - DEM. Donde > 0, el agua de lluvia no tiene salida por gravedad
   (encharcamiento).
3. Dirección de flujo D8 y acumulación de flujo (área que drena a cada celda) →
   índice topográfico de humedad TWI = ln(a / tan(pendiente)). TWI alto = fondos de
   valle y corredores de drenaje donde el escurrimiento se concentra.
4. Susceptibilidad ALTA = encharcamiento >= 0,5 m O TWI muy alto (p95).
   MEDIA = encharcamiento 0,25-0,5 m O TWI alto (p88-p95).
5. Se excluye el cauce permanente del río (agua, no pluvial).

LIMITACIONES: DEM de 30 m no capta la red de desagües pluviales, el alcantarillado
ni el encharcamiento a escala de calle; identifica lows topográficos a escala de
barrio. Donde la zona pluvial se solapa con la huella fluvial, ambas amenazas se
COMBINAN (compuesto). No sustituye un estudio hidráulico urbano (MOPC/ESSAP).

Salida: datos/geo/susceptibilidad-pluvial-asuncion.geojson
Validación: scratchpad/pluvial_validacion.png
"""
import os, json, heapq
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import numpy as np
import rioxarray, rasterio.features
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform as shp_transform
import pyproj
from pystac_client import Client
import planetary_computer as pc

AOI = [-57.66, -25.40, -57.46, -25.22]   # Asunción capital + metro interior
GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
SCRATCH = os.environ.get("SCRATCH", os.path.join(os.path.dirname(__file__), "..", "_scratch"))
MIN_AREA_M2, SIMPLIFY = 60_000, 0.0004

# ---------------------------------------------------------------- DEM
print("Descargando Copernicus DEM GLO-30 ...")
cat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
items = list(cat.search(collections=["cop-dem-glo-30"], bbox=AOI).items())
arrs = [rioxarray.open_rasterio(it.assets["data"].href, masked=True).rio.clip_box(*AOI).squeeze()
        for it in items]
dem = arrs[0] if len(arrs) == 1 else rioxarray.merge.merge_arrays(arrs).rio.clip_box(*AOI).squeeze()
z0 = dem.values.astype("float64")
transform, crs = dem.rio.transform(), dem.rio.crs
ny, nx = z0.shape
nodata = ~np.isfinite(z0)
# rellenar huecos con la mediana (para que el algoritmo corra); se re-enmascaran al final
zmed = np.nanmedian(z0)
z = np.where(nodata, zmed, z0)
print(f"DEM {ny}x{nx}  elev {np.nanmin(z0):.1f}-{np.nanmax(z0):.1f} m")

# tamaño de celda en metros (para pendiente y área específica)
lat_mid = (AOI[1] + AOI[3]) / 2
dy_m = abs(transform.e) * 111_320.0
dx_m = abs(transform.a) * 111_320.0 * np.cos(np.radians(lat_mid))
cell = (dx_m + dy_m) / 2

# ---------------------------------------------------------------- priority-flood
# Rellena depresiones y registra el ORDEN de procesamiento (jerarquía de drenaje).
print("Relleno de depresiones (priority-flood) ...")
filled = z.copy()
order = np.full((ny, nx), -1, dtype=np.int64)
closed = np.zeros((ny, nx), dtype=bool)
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
h = []
for i in range(ny):
    for j in (0, nx - 1):
        heapq.heappush(h, (z[i, j], i, j)); closed[i, j] = True
for j in range(nx):
    for i in (0, ny - 1):
        if not closed[i, j]:
            heapq.heappush(h, (z[i, j], i, j)); closed[i, j] = True
k = 0
while h:
    zc, i, j = heapq.heappop(h)
    order[i, j] = k; k += 1
    for di, dj in NB:
        ni, nj = i + di, j + dj
        if 0 <= ni < ny and 0 <= nj < nx and not closed[ni, nj]:
            closed[ni, nj] = True
            nz = z[ni, nj] if z[ni, nj] > zc else zc   # rellena hasta el nivel de vertido
            filled[ni, nj] = nz
            heapq.heappush(h, (nz, ni, nj))
depth = filled - z                                     # profundidad de depresión (m)

# ---------------------------------------------------------------- D8 + acumulación
# Receptor = vecino con menor (filled, order); garantizado por priority-flood.
print("Dirección de flujo D8 y acumulación ...")
BIG = filled.max() * 10 + 1
key = filled * 1e7 + order          # desempata llanuras por jerarquía de relleno
recv_i = np.arange(ny)[:, None].repeat(nx, 1)
recv_j = np.arange(nx)[None, :].repeat(ny, 0)
best = np.full((ny, nx), np.inf)
ri = recv_i.copy(); rj = recv_j.copy()
for di, dj in NB:
    ki = np.full((ny, nx), np.inf)
    sl = (slice(max(di, 0), ny + min(di, 0)), slice(max(dj, 0), nx + min(dj, 0)))
    dl = (slice(max(-di, 0), ny + min(-di, 0)), slice(max(-dj, 0), nx + min(-dj, 0)))
    ki[dl] = key[sl]
    better = ki < best
    best = np.where(better, ki, best)
    II = recv_i.copy(); JJ = recv_j.copy()
    II[dl] = recv_i[sl]; JJ[dl] = recv_j[sl]
    ri = np.where(better, II, ri); rj = np.where(better, JJ, rj)
has_recv = best < key                       # False solo en bordes/sumideros globales

# acumulación en orden descendente de 'order' (aguas arriba -> aguas abajo)
accum = np.ones((ny, nx), dtype=np.float64)
seq = np.argsort(order, axis=None)[::-1]     # de mayor a menor order
ri_f = ri.ravel(); rj_f = rj.ravel(); acc_f = accum.ravel(); hr_f = has_recv.ravel()
for idx in seq:
    if hr_f[idx]:
        r = ri_f[idx] * nx + rj_f[idx]
        acc_f[r] += acc_f[idx]
accum = acc_f.reshape(ny, nx)

# ---------------------------------------------------------------- TWI
gy, gx = np.gradient(filled, dy_m, dx_m)
slope = np.sqrt(gx * gx + gy * gy)
tanb = np.maximum(slope, 1e-3)
a_spec = accum * cell                          # área específica de captación (m)
twi = np.log(a_spec / tanb)

# ---------------------------------------------------------------- excluir cauce
def cargar(fns):
    gs = []
    for fn in fns:
        p = os.path.join(GEO, fn)
        if not os.path.exists(p):
            continue
        for f in json.load(open(p, encoding="utf-8"))["features"]:
            g = shape(f["geometry"]); gs.append(g if g.is_valid else g.buffer(0))
    return unary_union(gs) if gs else None

cauce = cargar(["cauce-permanente-s1.geojson"])
es_cauce = np.zeros((ny, nx), bool)
if cauce is not None and not cauce.is_empty:
    es_cauce = rasterio.features.geometry_mask([mapping(cauce)], (ny, nx), transform, invert=True)

# ---------------------------------------------------------------- clasificación
valido = np.isfinite(z0) & ~es_cauce
t95, t88 = np.percentile(twi[valido], 95), np.percentile(twi[valido], 88)
alta = valido & ((depth >= 0.5) | (twi >= t95))
media = valido & ~alta & ((depth >= 0.25) | (twi >= t88))
clase = np.zeros((ny, nx), np.uint8)
clase[media] = 1; clase[alta] = 2
print(f"TWI p88={t88:.2f} p95={t95:.2f} | celdas alta={int(alta.sum())} media={int(media.sum())}")
print(f"encharcamiento (depth>=0.5m): {int((valido&(depth>=0.5)).sum())} celdas "
      f"(~{(valido&(depth>=0.5)).sum()*cell*cell/1e6:.1f} km2)")

# ---------------------------------------------------------------- vectorizar
to_utm = pyproj.Transformer.from_crs(crs, "EPSG:32721", always_xy=True).transform
feats = []
for val, nombre in ((2, "alta"), (1, "media")):
    m = (clase == val)
    geoms = [shape(g) for g, v in rasterio.features.shapes(m.astype("uint8"), mask=m, transform=transform) if v == 1]
    if not geoms:
        continue
    u = unary_union(geoms)
    for p in getattr(u, "geoms", [u]):
        a = shp_transform(to_utm, p).area
        if a >= MIN_AREA_M2:
            feats.append({"type": "Feature",
                          "properties": {"clase": nombre, "area_km2": round(a / 1e6, 3)},
                          "geometry": mapping(p.simplify(SIMPLIFY).buffer(0))})
km2 = {c: round(sum(f["properties"]["area_km2"] for f in feats if f["properties"]["clase"] == c), 1)
       for c in ("alta", "media")}
out = os.path.join(GEO, "susceptibilidad-pluvial-asuncion.geojson")
json.dump({"type": "FeatureCollection",
           "metadata": {"desc": "Susceptibilidad a inundación pluvial (MODELO topográfico, no evento observado)",
                        "fuente": "Copernicus DEM GLO-30; priority-flood + D8 + TWI",
                        "aoi": AOI, "km2": km2,
                        "nota": "Proxy de escala de barrio; no incluye red de desagües. Solape con huella fluvial = amenaza combinada."},
           "features": feats}, open(out, "w", encoding="utf-8"), separators=(",", ":"))
print(f"guardado: {len(feats)} polígonos  | km2 {km2}  -> {out}")

# ---------------------------------------------------------------- validación PNG
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(16, 6))
    ext = [AOI[0], AOI[2], AOI[1], AOI[3]]
    ax[0].imshow(np.where(np.isfinite(z0), z0, np.nan), extent=ext, cmap="terrain"); ax[0].set_title("DEM (elevación)")
    ax[1].imshow(np.where(valido, twi, np.nan), extent=ext, cmap="Blues"); ax[1].set_title("TWI (humedad topográfica)")
    cl = np.where(clase == 2, 2, np.where(clase == 1, 1, np.nan))
    ax[2].imshow(np.where(np.isfinite(z0), z0, np.nan), extent=ext, cmap="Greys_r", alpha=0.6)
    ax[2].imshow(cl, extent=ext, cmap="autumn_r", vmin=1, vmax=2, alpha=0.7); ax[2].set_title("Susceptibilidad (alta=rojo, media)")
    os.makedirs(SCRATCH, exist_ok=True)
    png = os.path.join(SCRATCH, "pluvial_validacion.png")
    plt.tight_layout(); plt.savefig(png, dpi=110); print("PNG:", png)
except Exception as e:
    print("PNG omitido:", e)
