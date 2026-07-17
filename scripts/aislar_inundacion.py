"""
Aísla la INUNDACIÓN de 2015-16 restando el agua PERMANENTE del río.

Inundación = agua detectada por Sentinel-1 en el pico (2016-01-14)  Y NO  agua
permanente según el JRC Global Surface Water (ocurrencia >= 50 %, derivada de
1984-2021). El resto del agua del pico se clasifica como cauce permanente.

Se usa el JRC (37 años de imágenes) en vez de una sola fecha de aguas bajas
porque una referencia SAR de estación seca confunde suelo desnudo/campos lisos
con agua (da más "agua" que el propio pico) y eliminaría inundación real.

Fuente: Sentinel-1 RTC (Copernicus/ESA) + JRC GSW, vía Microsoft Planetary Computer.
Método: umbral gamma0 VV < -17 dB (piso -28 dB) para el agua del pico;
resta del agua permanente JRC alineada a la grilla del pico; polígonos > 10 ha.

Salidas (EPSG:4326):
  datos/geo/inundacion-s1-2016.geojson        (área anegada aislada)
  datos/geo/cauce-permanente-s1-2016.geojson  (cauce permanente en el pico)

LIMITACIONES: detección automática, no validada en campo, preliminar. Zonas
anegadas con agua rugosa por viento pueden no detectarse (falsos negativos).
"""
import os, json
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import numpy as np
import rioxarray, rasterio.warp
from rasterio.enums import Resampling
from rasterio.features import shapes
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform as shp_transform
import pyproj
from pystac_client import Client
import planetary_computer as pc

AOI = [-57.80, -25.50, -57.45, -25.05]
FECHA_PICO = "2016-01-14"
UMBRAL_DB, DB_MIN = -17.0, -28.0
OCC_PERMANENTE = 50          # JRC: ocurrencia >= 50% => agua permanente
MIN_AREA_M2, SIMPLIFY_M = 100_000, 30
GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")

cat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)

def water_da(fecha):
    item = next(iter(cat.search(collections=["sentinel-1-rtc"], bbox=AOI, datetime=fecha).items()))
    da = rioxarray.open_rasterio(item.assets["vv"].href, masked=True)
    crs = da.rio.crs
    da = da.rio.clip_box(*rasterio.warp.transform_bounds("EPSG:4326", crs, *AOI)).squeeze()
    g0 = da.values.astype("float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10 * np.log10(np.where(g0 > 0, g0, np.nan))
    w = ((np.isfinite(db)) & (db < UMBRAL_DB) & (db > DB_MIN)).astype("float32")
    out = da.copy(data=w)
    print(f"  {fecha}: {item.id[:40]} | agua px {int(w.sum())}")
    return out

def vectorizar(mask_bool, transform, crs, etiqueta):
    geoms = [shape(g) for g, v in shapes(mask_bool.astype("uint8"),
             mask=mask_bool, transform=transform) if v == 1]
    if not geoms:
        parts = []
    else:
        parts = [p for p in list(getattr(unary_union(geoms), "geoms", [unary_union(geoms)]))
                 if p.area >= MIN_AREA_M2]
        parts = [p.simplify(SIMPLIFY_M) for p in parts]
    to4326 = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    print(f"  {etiqueta}: {len(parts)} polígonos | {round(sum(p.area for p in parts)/1e6,1)} km2")
    return {"type": "FeatureCollection",
            "metadata": {"fuente": "Sentinel-1 RTC (Copernicus) + JRC Global Surface Water, vía Planetary Computer",
                         "pico": FECHA_PICO, "agua_permanente": f"JRC ocurrencia >= {OCC_PERMANENTE}%",
                         "capa": etiqueta, "metodo": "agua SAR del pico menos agua permanente JRC"},
            "features": [{"type": "Feature", "properties": {"area_km2": round(p.area/1e6, 3)},
                          "geometry": mapping(shp_transform(to4326, p))} for p in parts]}

print("Cargando escena del pico (Sentinel-1)...")
wp = water_da(FECHA_PICO)

print("Cargando agua permanente (JRC Global Surface Water)...")
jrc_item = next(iter(cat.search(collections=["jrc-gsw"], bbox=AOI).items()))
occ = rioxarray.open_rasterio(jrc_item.assets["occurrence"].href, masked=True)
occ = occ.rio.clip_box(*rasterio.warp.transform_bounds("EPSG:4326", occ.rio.crs, *AOI)).squeeze()
occ = occ.rio.reproject_match(wp, resampling=Resampling.bilinear)

peak = wp.values > 0.5
permanente = np.nan_to_num(occ.values) >= OCC_PERMANENTE
flood = peak & ~permanente
perm = peak & permanente
transform, crs = wp.rio.transform(), wp.rio.crs

json.dump(vectorizar(flood, transform, crs, "inundacion aislada"),
          open(os.path.join(GEO, "inundacion-s1-2016.geojson"), "w", encoding="utf-8"))
json.dump(vectorizar(perm, transform, crs, "cauce permanente"),
          open(os.path.join(GEO, "cauce-permanente-s1-2016.geojson"), "w", encoding="utf-8"))
print("listo.")
