"""
Detecta la huella de inundación de varios episodios de El Niño en Asunción con
el MISMO método que 2015-16, y elige la fecha de forma OBJETIVA.

Para cada episodio: escanea las escenas Sentinel-1 RTC de la ventana, calcula el
área de agua de cada una (VV < -17 dB, piso -28 dB), elige la de MAYOR extensión
(el pico real), y le resta el agua permanente del JRC Global Surface Water
(ocurrencia >= 50%). Guarda la inundación aislada por episodio.

Fuente: Sentinel-1 RTC + JRC GSW, vía Microsoft Planetary Computer.
Salida: datos/geo/inundacion-<episodio>-s1.geojson (EPSG:4326).
LIMITACIONES: idénticas a scripts/aislar_inundacion.py (automático, preliminar).
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
UMBRAL_DB, DB_MIN, OCC_PERMANENTE = -17.0, -28.0, 50
MIN_AREA_M2, SIMPLIFY_M = 100_000, 30
GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")

# Todos en la MISMA órbita relativa (68 descendente) para comparabilidad: sobre
# esta zona capta el río Paraguay de forma limpia (la órbita 141 lo subdetecta).
RELORB = 68
EPISODIOS = [
    ("2015-16", "2015-12-15/2016-02-15"),
    ("2018-19", "2019-05-01/2019-07-15"),
    ("2023-24", "2023-12-01/2024-06-30"),
]

cat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)

def leer_vv(item):
    da = rioxarray.open_rasterio(item.assets["vv"].href, masked=True)
    crs = da.rio.crs
    da = da.rio.clip_box(*rasterio.warp.transform_bounds("EPSG:4326", crs, *AOI)).squeeze()
    return da

def water_mask(da):
    g0 = da.values.astype("float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10 * np.log10(np.where(g0 > 0, g0, np.nan))
    return (np.isfinite(db) & (db < UMBRAL_DB) & (db > DB_MIN))

def area_km2(mask, da):
    a, e = da.rio.transform()[0], da.rio.transform()[4]
    return mask.sum() * abs(a * e) / 1e6

def occ_permanente(da_ref):
    it = next(iter(cat.search(collections=["jrc-gsw"], bbox=AOI).items()))
    occ = rioxarray.open_rasterio(it.assets["occurrence"].href, masked=True)
    occ = occ.rio.clip_box(*rasterio.warp.transform_bounds("EPSG:4326", occ.rio.crs, *AOI)).squeeze()
    return np.nan_to_num(occ.rio.reproject_match(da_ref, resampling=Resampling.bilinear).values) >= OCC_PERMANENTE

def vectorizar(mask, transform, crs):
    geoms = [shape(g) for g, v in shapes(mask.astype("uint8"), mask=mask, transform=transform) if v == 1]
    if not geoms:
        return []
    parts = [p for p in list(getattr(unary_union(geoms), "geoms", [unary_union(geoms)])) if p.area >= MIN_AREA_M2]
    to4326 = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    return [{"type": "Feature", "properties": {"area_km2": round(p.area / 1e6, 3)},
             "geometry": mapping(shp_transform(to4326, p.simplify(SIMPLIFY_M)))} for p in parts]

for label, rango in EPISODIOS:
    print(f"=== {label} ({rango}) ===")
    items = sorted(cat.search(collections=["sentinel-1-rtc"], bbox=AOI, datetime=rango,
                   query={"sat:orbit_state": {"eq": "descending"},
                          "sat:relative_orbit": {"eq": RELORB}}).items(), key=lambda x: x.datetime)
    vistos, unicos = set(), []
    for it in items:
        d = it.datetime.date()
        if d not in vistos:
            vistos.add(d); unicos.append(it)
    mejor = None
    for it in unicos:
        da = leer_vv(it)
        km2 = area_km2(water_mask(da), da)
        print(f"  {it.datetime.date()}: agua {km2:5.1f} km2")
        if mejor is None or km2 > mejor[0]:
            mejor = (km2, it, da)
    km2, it, da = mejor
    print(f"  -> PICO: {it.datetime.date()} ({km2:.1f} km2)")
    perm = occ_permanente(da)
    agua = water_mask(da)
    flood = agua & ~perm
    feats = vectorizar(flood, da.rio.transform(), da.rio.crs)

    if label == "2015-16":  # guardar una capa de cauce permanente de referencia
        pfeats = vectorizar(agua & perm, da.rio.transform(), da.rio.crs)
        json.dump({"type": "FeatureCollection",
                   "metadata": {"capa": "cauce permanente", "fuente": "JRC GSW (occ>=50%) ∩ agua Sentinel-1"},
                   "features": pfeats},
                  open(os.path.join(GEO, "cauce-permanente-s1.geojson"), "w", encoding="utf-8"),
                  separators=(",", ":"))
        print(f"  cauce permanente: {len(pfeats)} polígonos")
    fc = {"type": "FeatureCollection",
          "metadata": {"episodio": label, "fuente": "Sentinel-1 RTC + JRC GSW vía Planetary Computer",
                       "fecha_pico": str(it.datetime.date()), "escena": it.id,
                       "metodo": "agua SAR (VV<-17dB) menos agua permanente JRC (occ>=50%)"},
          "features": feats}
    out = os.path.join(GEO, f"inundacion-{label}-s1.geojson")
    json.dump(fc, open(out, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"  guardado: {os.path.basename(out)} | {len(feats)} polígonos | "
          f"{round(sum(f['properties']['area_km2'] for f in feats),1)} km2 inundacion")
