"""
Zona de anegamiento recurrente para varias zonas ribereñas prioritarias.

Mismo método que Ñeembucú (frecuencia de agua): para cada zona se toma el agua de
mayo (alta de la cuenca) de 2019-2024, y se define como zona de anegamiento el
área con agua en >= 2 de los años, menos el cauce permanente (JRC GSW). Es un
mapa de hazard recurrente, no un evento único.

Fuente: Sentinel-1 RTC + JRC GSW, vía Microsoft Planetary Computer.
Salida: datos/geo/anegamiento-<id>-s1.geojson (EPSG:4326).
LIMITACIONES: detección automática, preliminar, no validada en campo.
"""
import os, json, time
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

ZONAS = [
    {"id": "fuerteolimpo", "nombre": "Fuerte Olimpo", "aoi": [-58.02, -21.15, -57.72, -20.92]},
]
YEARS = [2019, 2020, 2021, 2022, 2023, 2024]
OVERVIEW = 1
UMBRAL_DB, DB_MIN, OCC_PERM = -17.0, -28.0, 50
MIN_AREA_M2, SIMPLIFY_M, RECUR_MIN = 50_000, 40, 2
GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")


def cat_open():
    for i in range(6):
        try:
            return Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
        except Exception:
            print(f"  PC no responde, reintento {i}..."); time.sleep(10)
    raise SystemExit("Planetary Computer no disponible")


cat = cat_open()


def frames_por_fecha(aoi, rango):
    """Frame de mayor cobertura del AOI por fecha en el rango."""
    aoi_box = box(*aoi)
    items = list(cat.search(collections=["sentinel-1-rtc"], bbox=aoi, datetime=rango).items())
    porfecha = {}
    for it in items:
        inter = shape(it.geometry).intersection(aoi_box).area
        if inter <= 0:
            continue
        d = it.datetime.date()
        if d not in porfecha or inter > porfecha[d][0]:
            porfecha[d] = (inter, it)
    return [v[1] for v in porfecha.values()]


def pico_agua(aoi, rango):
    """Entre las fechas del rango, devuelve (item, w, da) con MÁS agua."""
    mejor = None
    for it in frames_por_fecha(aoi, rango):
        w, da = water_da(it, aoi)
        a = float((w.values > 0.5).sum())
        if mejor is None or a > mejor[0]:
            mejor = (a, it, w, da)
    return mejor


def water_da(item, aoi):
    da = rioxarray.open_rasterio(item.assets["vv"].href, masked=True, overview_level=OVERVIEW)
    da = da.rio.clip_box(*rasterio.warp.transform_bounds("EPSG:4326", da.rio.crs, *aoi)).squeeze()
    g0 = da.values.astype("float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10 * np.log10(np.where(g0 > 0, g0, np.nan))
    w = (np.isfinite(db) & (db < UMBRAL_DB) & (db > DB_MIN)).astype("float32")
    return da.copy(data=w), da


for z in ZONAS:
    print(f"=== {z['nombre']} ===")
    aoi = z["aoi"]
    ref_da, count, n_ok = None, None, 0
    for y in YEARS:
        res = pico_agua(aoi, f"{y}-04-15/{y}-06-30")
        if res is None:
            print(f"  {y}: sin escena"); continue
        _, it, w, da = res
        if ref_da is None:
            ref_da = da
            count = (w.values > 0.5).astype("int16")
        else:
            wr = w.rio.reproject_match(ref_da, resampling=Resampling.nearest)
            count = count + (np.nan_to_num(wr.values) > 0.5).astype("int16")
        n_ok += 1
        km2 = float((w.values > 0.5).sum()) * (abs(da.rio.transform()[0] * da.rio.transform()[4]) / 1e6)
        print(f"  {y}: {it.datetime.date()} agua {km2:.1f} km2")
    if ref_da is None or n_ok < 3:
        print(f"  datos insuficientes ({n_ok} años), se omite"); continue

    jit = next(iter(cat.search(collections=["jrc-gsw"], bbox=aoi).items()))
    occ = rioxarray.open_rasterio(jit.assets["occurrence"].href, masked=True)
    occ = occ.rio.clip_box(*rasterio.warp.transform_bounds("EPSG:4326", occ.rio.crs, *aoi)).squeeze()
    occ = np.nan_to_num(occ.rio.reproject_match(ref_da, resampling=Resampling.bilinear).values)
    zona = (count >= RECUR_MIN) & (occ < OCC_PERM)

    geoms = [shape(g) for g, v in shapes(zona.astype("uint8"), mask=zona, transform=ref_da.rio.transform()) if v == 1]
    parts = [p for p in list(getattr(unary_union(geoms), "geoms", [unary_union(geoms)])) if p.area >= MIN_AREA_M2] if geoms else []
    to4326 = pyproj.Transformer.from_crs(ref_da.rio.crs, "EPSG:4326", always_xy=True).transform
    feats = [{"type": "Feature", "properties": {"area_km2": round(p.area / 1e6, 2)},
              "geometry": mapping(shp_transform(to4326, p.simplify(SIMPLIFY_M)))} for p in parts]
    fc = {"type": "FeatureCollection",
          "metadata": {"zona": z["nombre"], "fuente": "Sentinel-1 RTC + JRC GSW vía Planetary Computer",
                       "metodo": f"agua en >= {RECUR_MIN} de mayos {YEARS} menos permanente JRC (occ>={OCC_PERM}%)",
                       "nota": "Zona de anegamiento recurrente. Preliminar, no validado en campo."},
          "features": feats}
    out = os.path.join(GEO, f"anegamiento-{z['id']}-s1.geojson")
    json.dump(fc, open(out, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"  -> {os.path.basename(out)} | {len(feats)} polígonos | {round(sum(f['properties']['area_km2'] for f in feats),1)} km2")
