"""
Deriva la extensión de agua sobre Asunción durante la crecida de enero de 2016
a partir de imágenes Sentinel-1 (radar SAR), y la exporta como GeoJSON.

FUENTE   : Sentinel-1 RTC (gamma0 terreno-corregido), Copernicus / ESA,
           accedido vía Microsoft Planetary Computer (STAC, acceso abierto).
ESCENA   : 2016-01-14 (la más cercana al pico del río del 2016-01-07; el
           12-ene no tiene escena Sentinel-1 sobre el área).
MÉTODO   : el agua abierta refleja poca señal al radar -> umbral de
           retrodispersión VV (gamma0) < -17 dB. Se descarta el relleno de
           borde de escena (< -28 dB) y las manchas menores a 5 ha.
SALIDA   : datos/geo/agua-s1-20160114.geojson (EPSG:4326).

LIMITACIONES (leer): detección AUTOMÁTICA, no validada en campo. Es
"extensión de agua detectada", que incluye el cauce permanente del río además
del área anegada (para aislar solo la inundación haría falta diferenciar contra
una fecha de aguas bajas). La cobertura es irregular: el viento sobre el agua
puede elevar la señal y hacer que zonas realmente inundadas no se detecten.
Producto PRELIMINAR, de contexto; no sustituye cartografía oficial (SEN/DINAC).

Requisitos: pip install pystac-client planetary-computer rioxarray rasterio shapely pyproj numpy
Uso:        python scripts/derivar_huella_agua.py
"""
import os, json
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"

import numpy as np
import rioxarray, rasterio.warp
from rasterio.features import shapes
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform as shp_transform
import pyproj
from pystac_client import Client
import planetary_computer as pc

AOI = [-57.80, -25.50, -57.45, -25.05]   # lon/lat: río Paraguay + Asunción metro
FECHA = "2016-01-14"
UMBRAL_DB = -17.0        # agua: gamma0 VV por debajo de este valor
DB_MIN = -28.0           # por debajo => relleno/nodata (borde de escena), no agua
MIN_AREA_M2 = 50_000     # descartar manchas menores a 5 ha
SIMPLIFY_M = 30
SALIDA = os.path.join(os.path.dirname(__file__), "..", "datos", "geo",
                      "agua-s1-20160114.geojson")

def main():
    cat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                      modifier=pc.sign_inplace)
    item = next(iter(cat.search(collections=["sentinel-1-rtc"],
                                bbox=AOI, datetime=FECHA).items()))
    print("escena:", item.id)

    da = rioxarray.open_rasterio(item.assets["vv"].href, masked=True)
    crs = da.rio.crs
    bounds = rasterio.warp.transform_bounds("EPSG:4326", crs, *AOI)
    da = da.rio.clip_box(*bounds).squeeze()
    g0 = da.values.astype("float32")

    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10 * np.log10(np.where(g0 > 0, g0, np.nan))
    water = np.where(np.isfinite(db) & (db < UMBRAL_DB) & (db > DB_MIN), 1, 0).astype("uint8")

    transform = da.rio.transform()
    geoms = [shape(g) for g, v in shapes(water, mask=water.astype(bool), transform=transform) if v == 1]
    parts = [p for p in list(getattr(unary_union(geoms), "geoms", [unary_union(geoms)]))
             if p.area >= MIN_AREA_M2]
    parts = [p.simplify(SIMPLIFY_M) for p in parts]
    print("polígonos:", len(parts), "| área km2:", round(sum(p.area for p in parts) / 1e6, 1))

    to4326 = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    fc = {"type": "FeatureCollection",
          "metadata": {"fuente": "Sentinel-1 RTC (Copernicus/ESA) vía Microsoft Planetary Computer",
                       "escena": item.id, "fecha": FECHA,
                       "metodo": f"umbral gamma0 VV < {UMBRAL_DB} dB (piso {DB_MIN} dB)",
                       "nota": "Extensión de agua detectada (automática, preliminar); incluye cauce permanente"},
          "features": [{"type": "Feature",
                        "properties": {"area_km2": round(p.area / 1e6, 3)},
                        "geometry": mapping(shp_transform(to4326, p))} for p in parts]}
    json.dump(fc, open(SALIDA, "w", encoding="utf-8"))
    print("guardado:", os.path.normpath(SALIDA))

if __name__ == "__main__":
    main()
