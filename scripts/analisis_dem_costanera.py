"""
Análisis de elevación (DEM) para el efecto de defensa de la Costanera en Asunción.

Método (relativo, sin datum absoluto del río):
1. DEM: Copernicus GLO-30 (30 m) sobre los bañados de Asunción.
2. "Cota de inundación" calibrada con la HUELLA satelital observada (Sentinel-1):
   el percentil 90 de la elevación de lo efectivamente inundado (2015-16, 2018-19).
3. Zonas bajas (DEM <= umbral) que NO figuran en la huella observada = CANDIDATAS
   A ESTAR PROTEGIDAS (bajas pero no inundadas: defensa o desconexión hidráulica).
4. Se confirma que la Costanera es un terraplén más alto que los bañados detrás.

LIMITACIONES: DEM de 30 m (no capta microtopografía ni edificios); umbral relativo
a lo observado, no a una cota absoluta; "protegida" incluye cualquier causa (la
Costanera u otra), no solo el terraplén; falta la cota de coronamiento (MOPC).

Salida: datos/geo/protegido-costanera.geojson
"""
import os, json
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import numpy as np
import rioxarray, rasterio.features
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform as shp_transform
import pyproj
from pystac_client import Client
import planetary_computer as pc

AOI = [-57.70, -25.36, -57.55, -25.20]
GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
MIN_AREA_M2, SIMPLIFY_M = 40_000, 30

cat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
item = next(iter(cat.search(collections=["cop-dem-glo-30"], bbox=AOI).items()))
dem = rioxarray.open_rasterio(item.assets["data"].href, masked=True).rio.clip_box(*AOI).squeeze()
z = dem.values.astype("float32")
transform, crs = dem.rio.transform(), dem.rio.crs

def cargar(fns):
    gs = []
    for fn in fns:
        for f in json.load(open(os.path.join(GEO, fn), encoding="utf-8"))["features"]:
            g = shape(f["geometry"]); gs.append(g if g.is_valid else g.buffer(0))
    return unary_union(gs)

# --- huella observada -> umbral de cota de inundación ---
huella = cargar(["inundacion-2015-16-s1.geojson", "inundacion-2018-19-s1.geojson"])
obs = rasterio.features.geometry_mask([mapping(huella)], z.shape, transform, invert=True)
z_obs = z[obs & np.isfinite(z)]
umbral = float(np.percentile(z_obs, 90))
print(f"cota de inundación (p90 observado): {umbral:.1f} m  | mediana bañado inundado: {np.median(z_obs):.1f} m")

# --- Costanera: elevación (¿es terraplén?) ---
infra = json.load(open(os.path.join(GEO, "infraestructura-asuncion.geojson"), encoding="utf-8"))
cost = [shape(f["geometry"]) for f in infra["features"]
        if f["properties"]["categoria"].startswith("Defensa")]
cost_u = unary_union(cost)
cost_mask = rasterio.features.geometry_mask([mapping(cost_u.buffer(0.0004))], z.shape, transform, invert=True)
z_cost = z[cost_mask & np.isfinite(z)]
print(f"elevación de la Costanera: mediana {np.median(z_cost):.1f} m  (p25 {np.percentile(z_cost,25):.1f}) "
      f"-> {np.median(z_cost)-np.median(z_obs):+.1f} m sobre el bañado inundado")

# --- candidatas a protegidas: bajas (<=umbral), NO inundadas y JUNTO a la
#     Costanera (franja que el terraplén plausiblemente protege, ~500 m) ---
cerca_cost = rasterio.features.geometry_mask([mapping(cost_u.buffer(0.0045))], z.shape, transform, invert=True)
protegido = (z <= umbral) & np.isfinite(z) & ~obs & cerca_cost
print(f"franja baja no inundada junto a la Costanera: {int(protegido.sum())} celdas "
      f"({protegido.sum()*30*30/1e6:.1f} km2 aprox)")

# El DEM está en grados (EPSG:4326): vectorizamos ahí y medimos área en UTM 21S.
geoms = [shape(g) for g, v in rasterio.features.shapes(protegido.astype("uint8"),
         mask=protegido, transform=transform) if v == 1]
to_utm = pyproj.Transformer.from_crs(crs, "EPSG:32721", always_xy=True).transform
feats = []
for p in getattr(unary_union(geoms), "geoms", [unary_union(geoms)]):
    a = shp_transform(to_utm, p).area
    if a >= MIN_AREA_M2:
        feats.append({"type": "Feature", "properties": {"area_km2": round(a / 1e6, 3)},
                      "geometry": mapping(p.simplify(0.0003))})
out = os.path.join(GEO, "protegido-costanera.geojson")
json.dump({"type": "FeatureCollection",
           "metadata": {"desc": "Zonas bajas (DEM<=p90 huella) NO inundadas: candidatas a protegidas",
                        "fuente": "Copernicus DEM GLO-30 + huellas Sentinel-1", "umbral_m": round(umbral, 1)},
           "features": feats}, open(out, "w", encoding="utf-8"), separators=(",", ":"))
print(f"guardado: {len(feats)} polígonos candidatos a protegidos")
