"""
Huella de inundación de Pilar/Ñeembucú (crecida de 2024) por ANOMALÍA TEMPORAL.

En una zona de humedal (Esteros del Ñeembucú) restar solo el agua permanente no
basta: el agua estacional normal de mayo se confundiría con inundación. Aquí se
compara el agua de mayo-2024 contra el agua típica de mayo de años previos:

  1. Agua en el pico de mayo-2024 (Sentinel-1, máx. extensión).
  2. Para cada mayo de 2019-2023: máscara de agua sobre el mismo AOI y grilla.
  3. "Normalmente húmedo en mayo" = agua en la MAYORÍA de los años base
     (>= 3 de 5). El voto por mayoría es robusto a mayo-2019 (que también fue
     inundación) y a la sequía de La Niña de 2020-21.
  4. Inundación 2024 = agua 2024  Y NO  normalmente húmedo  (y no permanente JRC).

Fuente: Sentinel-1 RTC + JRC GSW, vía Microsoft Planetary Computer.
Salida: datos/geo/inundacion-neembucu-2023-24-s1.geojson (EPSG:4326).
LIMITACIONES: detección automática, preliminar, no validada en campo.
"""
import os, json, time, math
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import numpy as np
import rioxarray, rasterio.warp
from rasterio.enums import Resampling
from rasterio.features import shapes
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union, transform as shp_transform
import pyproj
from pystac_client import Client
import planetary_computer as pc

AOI = [-58.55, -27.05, -57.95, -26.15]
OVERVIEW = 1
RELORB = 68
UMBRAL_DB, DB_MIN = -17.0, -28.0
OCC_PERMANENTE = 50
MIN_AREA_M2, SIMPLIFY_M = 100_000, 40
ANIO_FLOOD = "2024-05-01/2024-05-31"
BASE_YEARS = [2019, 2020, 2021, 2022, 2023]
GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
AOI_BOX = box(*AOI)

def cat_open():
    for i in range(6):
        try:
            return Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
        except Exception:
            print(f"  PC no responde, reintento {i}..."); time.sleep(10)
    raise SystemExit("Planetary Computer no disponible")

cat = cat_open()

def mejor_frame(rango, max_agua=False):
    """Frame de mayor cobertura del AOI en el rango (relorb fijo). Si max_agua,
    entre las fechas devuelve la de mayor extensión de agua."""
    items = [it for it in cat.search(collections=["sentinel-1-rtc"], bbox=AOI, datetime=rango,
             query={"sat:relative_orbit": {"eq": RELORB}}).items()]
    if not items:
        return None
    porfecha = {}
    for it in items:
        inter = shape(it.geometry).intersection(AOI_BOX).area
        d = it.datetime.date()
        if d not in porfecha or inter > porfecha[d][0]:
            porfecha[d] = (inter, it)
    cand = [v[1] for v in porfecha.values()]
    if not max_agua:
        return max(cand, key=lambda it: shape(it.geometry).intersection(AOI_BOX).area)
    mejor = None
    for it in cand:
        w, _ = water_da(it)
        a = float(w.values.sum())
        if mejor is None or a > mejor[0]:
            mejor = (a, it)
    return mejor[1]

def water_da(item):
    da = rioxarray.open_rasterio(item.assets["vv"].href, masked=True, overview_level=OVERVIEW)
    da = da.rio.clip_box(*rasterio.warp.transform_bounds("EPSG:4326", da.rio.crs, *AOI)).squeeze()
    g0 = da.values.astype("float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10 * np.log10(np.where(g0 > 0, g0, np.nan))
    w = (np.isfinite(db) & (db < UMBRAL_DB) & (db > DB_MIN)).astype("float32")
    return da.copy(data=w), da

# --- Referencia: pico de mayo-2024 ---
ref_item = mejor_frame(ANIO_FLOOD, max_agua=True)
print("referencia 2024:", ref_item.datetime.date())
w2024, ref_da = water_da(ref_item)
ref_mask = w2024.values > 0.5

# --- Base temporal: mayos previos ---
conteo = np.zeros_like(ref_mask, dtype="int16")
n_ok = 0
for y in BASE_YEARS:
    it = mejor_frame(f"{y}-05-01/{y}-05-31")
    if it is None:
        print(f"  {y}: sin escena, se omite"); continue
    wy, _ = water_da(it)
    wy = wy.rio.reproject_match(ref_da, resampling=Resampling.nearest)
    conteo += (np.nan_to_num(wy.values) > 0.5).astype("int16")
    n_ok += 1
    print(f"  base {y}: {it.datetime.date()} ok")
umbral_mayoria = math.ceil(n_ok / 2)
normal = conteo >= umbral_mayoria
print(f"años base con datos: {n_ok} | 'normalmente húmedo' = agua en >= {umbral_mayoria} años")

# --- JRC permanente (red de seguridad para el cauce) ---
jit = next(iter(cat.search(collections=["jrc-gsw"], bbox=AOI).items()))
occ = rioxarray.open_rasterio(jit.assets["occurrence"].href, masked=True)
occ = occ.rio.clip_box(*rasterio.warp.transform_bounds("EPSG:4326", occ.rio.crs, *AOI)).squeeze()
occ = np.nan_to_num(occ.rio.reproject_match(ref_da, resampling=Resampling.bilinear).values)
permanente = occ >= OCC_PERMANENTE

px_km2 = abs(ref_da.rio.transform()[0] * ref_da.rio.transform()[4]) / 1e6
to4326 = pyproj.Transformer.from_crs(ref_da.rio.crs, "EPSG:4326", always_xy=True).transform

def vectorizar(mask):
    geoms = [shape(g) for g, v in shapes(mask.astype("uint8"), mask=mask, transform=ref_da.rio.transform()) if v == 1]
    if not geoms:
        return []
    parts = [p for p in list(getattr(unary_union(geoms), "geoms", [unary_union(geoms)])) if p.area >= MIN_AREA_M2]
    return [{"type": "Feature", "properties": {"area_km2": round(p.area / 1e6, 2)},
             "geometry": mapping(shp_transform(to4326, p.simplify(SIMPLIFY_M)))} for p in parts]

def guardar(feats, nombre, metodo, nota):
    fc = {"type": "FeatureCollection",
          "metadata": {"region": "Pilar/Ñeembucú", "fuente": "Sentinel-1 RTC + JRC GSW vía Planetary Computer",
                       "fecha_pico": str(ref_item.datetime.date()), "metodo": metodo, "nota": nota},
          "features": feats}
    json.dump(fc, open(os.path.join(GEO, nombre), "w", encoding="utf-8"), separators=(",", ":"))
    print(f"guardado: {nombre} | {len(feats)} polígonos | {round(sum(f['properties']['area_km2'] for f in feats),1)} km2")

# (a) Anomalía 2024: agua de 2024 que NO es normalmente húmeda en mayo
anomalia = ref_mask & ~normal & ~permanente
print(f"agua 2024: {round(ref_mask.sum()*px_km2,1)} km2 | anomalía 2024: {round(anomalia.sum()*px_km2,1)} km2")
guardar(vectorizar(anomalia), "anomalia-neembucu-2024-s1.geojson",
        f"anomalía temporal: agua may-2024 menos agua típica de mayo {BASE_YEARS} (voto mayoría) menos permanente JRC",
        "Excedente anómalo de 2024 (mayormente interior de esteros). Preliminar, no validado.")

# (b) Zona de anegamiento RECURRENTE (hazard): agua en >= 2 de 6 mayos (2019-2024),
#     excluyendo el cauce permanente. Es la que captura la exposición de Pilar/Alberdi.
conteo_all = conteo + ref_mask.astype("int16")
recurrente = (conteo_all >= 2) & ~permanente
print(f"zona recurrente (>=2 de {n_ok+1} mayos): {round(recurrente.sum()*px_km2,1)} km2")
guardar(vectorizar(recurrente), "zona-anegamiento-neembucu-s1.geojson",
        f"frecuencia de anegamiento: agua en >= 2 de {n_ok+1} mayos (2019-2024) menos permanente JRC",
        "Zona de anegamiento recurrente (hazard). Preliminar, no validado en campo.")
