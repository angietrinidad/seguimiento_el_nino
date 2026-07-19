"""
Susceptibilidad a inundación PLUVIAL (por lluvia y drenaje insuficiente) derivada
de la topografía (Copernicus DEM GLO-30), para varias ciudades ribereñas.

A diferencia de la inundación FLUVIAL (desborde del río, mapeada con Sentinel-1), la
pluvial ocurre donde el agua de lluvia se acumula por el relieve y la falta de
drenaje. Este análisis NO observa una inundación: MODELA dónde el terreno favorece
el encharcamiento y la concentración del escurrimiento. Es SUSCEPTIBILIDAD (proxy
topográfico), no un evento observado.

Método (por ciudad): DEM -> relleno de depresiones (priority-flood) -> dirección de
flujo D8 y acumulación -> índice topográfico de humedad TWI. Susceptibilidad ALTA =
encharcamiento >= 0,5 m O TWI muy alto (p95); MEDIA = 0,25 m O TWI alto (p88).

LIMITACIONES: DEM de 30 m no capta la red de desagües ni el anegamiento a escala de
calle; identifica lows topográficos a escala de barrio. Solape con la huella fluvial
= amenaza combinada. No sustituye un estudio hidráulico urbano.

Salida: datos/geo/susceptibilidad-pluvial-<cid>.geojson (una por ciudad)
Uso: py scripts/analisis_pluvial_dem.py [cid1 cid2 ...]  (por defecto: todas)
Validación: scratchpad/pluvial_<cid>.png
"""
import os, json, heapq, sys, time
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import numpy as np
import rioxarray, rasterio.features
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, transform as shp_transform
import pyproj
from pystac_client import Client
import planetary_computer as pc

GEO = os.path.join(os.path.dirname(__file__), "..", "datos", "geo")
SCRATCH = os.environ.get("SCRATCH", os.path.join(os.path.dirname(__file__), "..", "_scratch"))
MIN_AREA_M2, SIMPLIFY = 60_000, 0.0004

# ciudades ribereñas: id -> (nombre, AOI [oeste, sur, este, norte])
CIUDADES = {
    "asuncion":        ("Asunción y metro interior", [-57.66, -25.40, -57.46, -25.22]),
    "ciudad-del-este": ("Ciudad del Este", [-54.70, -25.56, -54.56, -25.44]),
    "encarnacion":     ("Encarnación", [-55.94, -27.40, -55.80, -27.28]),
    "concepcion":      ("Concepción", [-57.50, -23.48, -57.36, -23.36]),
    "pilar":           ("Pilar", [-58.38, -26.92, -58.24, -26.80]),
}
CAT = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def cargar(fns, aoi_geom):
    gs = []
    for fn in fns:
        p = os.path.join(GEO, fn)
        if not os.path.exists(p):
            continue
        for f in json.load(open(p, encoding="utf-8"))["features"]:
            g = shape(f["geometry"]); g = g if g.is_valid else g.buffer(0)
            if g.intersects(aoi_geom):
                gs.append(g)
    return unary_union(gs) if gs else None


def descargar_dem(AOI, intentos=5):
    """Búsqueda + apertura del DEM con reintentos (Planetary Computer da 504 a veces)."""
    ult = None
    for k in range(intentos):
        try:
            items = list(CAT.search(collections=["cop-dem-glo-30"], bbox=AOI).items())
            if not items:
                return None
            return [rioxarray.open_rasterio(it.assets["data"].href, masked=True).rio.clip_box(*AOI).squeeze()
                    for it in items]
        except Exception as e:
            ult = e; espera = 8 * (k + 1)
            print(f"  intento {k+1} falló ({type(e).__name__}); reintento en {espera}s")
            time.sleep(espera)
    raise ult


def procesar(cid, nombre, AOI):
    print(f"\n=== {nombre} ({cid}) — descargando DEM ...")
    arrs = descargar_dem(AOI)
    if not arrs:
        print("  sin cobertura DEM, se omite"); return None
    dem = arrs[0] if len(arrs) == 1 else rioxarray.merge.merge_arrays(arrs).rio.clip_box(*AOI).squeeze()
    z0 = dem.values.astype("float64")
    transform, crs = dem.rio.transform(), dem.rio.crs
    ny, nx = z0.shape
    nodata = ~np.isfinite(z0)
    z = np.where(nodata, np.nanmedian(z0), z0)
    print(f"  DEM {ny}x{nx}  elev {np.nanmin(z0):.1f}-{np.nanmax(z0):.1f} m")

    lat_mid = (AOI[1] + AOI[3]) / 2
    dy_m = abs(transform.e) * 111_320.0
    dx_m = abs(transform.a) * 111_320.0 * np.cos(np.radians(lat_mid))
    cell = (dx_m + dy_m) / 2

    # priority-flood: rellena depresiones y registra el orden de procesamiento
    filled = z.copy()
    order = np.full((ny, nx), -1, dtype=np.int64)
    closed = np.zeros((ny, nx), dtype=bool)
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
                nz = z[ni, nj] if z[ni, nj] > zc else zc
                filled[ni, nj] = nz
                heapq.heappush(h, (nz, ni, nj))
    depth = filled - z

    # D8 + acumulación
    key = filled * 1e7 + order
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
    has_recv = best < key
    accum = np.ones((ny, nx), dtype=np.float64)
    seq = np.argsort(order, axis=None)[::-1]
    ri_f = ri.ravel(); rj_f = rj.ravel(); acc_f = accum.ravel(); hr_f = has_recv.ravel()
    for idx in seq:
        if hr_f[idx]:
            acc_f[ri_f[idx] * nx + rj_f[idx]] += acc_f[idx]
    accum = acc_f.reshape(ny, nx)

    # TWI
    gy, gx = np.gradient(filled, dy_m, dx_m)
    slope = np.sqrt(gx * gx + gy * gy)
    twi = np.log((accum * cell) / np.maximum(slope, 1e-3))

    # excluir cauce permanente si lo hay en el AOI
    aoi_geom = shape({"type": "Polygon", "coordinates": [[
        [AOI[0], AOI[1]], [AOI[2], AOI[1]], [AOI[2], AOI[3]], [AOI[0], AOI[3]], [AOI[0], AOI[1]]]]})
    cauce = cargar(["cauce-permanente-s1.geojson"], aoi_geom)
    es_cauce = np.zeros((ny, nx), bool)
    if cauce is not None and not cauce.is_empty:
        es_cauce = rasterio.features.geometry_mask([mapping(cauce)], (ny, nx), transform, invert=True)

    valido = np.isfinite(z0) & ~es_cauce
    t95, t88 = np.percentile(twi[valido], 95), np.percentile(twi[valido], 88)
    alta = valido & ((depth >= 0.5) | (twi >= t95))
    media = valido & ~alta & ((depth >= 0.25) | (twi >= t88))
    clase = np.zeros((ny, nx), np.uint8)
    clase[media] = 1; clase[alta] = 2

    # vectorizar
    to_utm = pyproj.Transformer.from_crs(crs, "EPSG:32721", always_xy=True).transform
    feats = []
    for val, nom in ((2, "alta"), (1, "media")):
        m = (clase == val)
        geoms = [shape(g) for g, v in rasterio.features.shapes(m.astype("uint8"), mask=m, transform=transform) if v == 1]
        if not geoms:
            continue
        u = unary_union(geoms)
        for pgeom in getattr(u, "geoms", [u]):
            a = shp_transform(to_utm, pgeom).area
            if a >= MIN_AREA_M2:
                feats.append({"type": "Feature",
                              "properties": {"clase": nom, "area_km2": round(a / 1e6, 3)},
                              "geometry": mapping(pgeom.simplify(SIMPLIFY).buffer(0))})
    km2 = {c: round(sum(f["properties"]["area_km2"] for f in feats if f["properties"]["clase"] == c), 1)
           for c in ("alta", "media")}
    out = os.path.join(GEO, f"susceptibilidad-pluvial-{cid}.geojson")
    json.dump({"type": "FeatureCollection",
               "metadata": {"desc": f"Susceptibilidad pluvial (MODELO topográfico) — {nombre}",
                            "ciudad": nombre, "fuente": "Copernicus DEM GLO-30; priority-flood + D8 + TWI",
                            "aoi": AOI, "km2": km2,
                            "nota": "Proxy de escala de barrio; no incluye red de desagües. Solape con huella fluvial = amenaza combinada."},
               "features": feats}, open(out, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"  guardado {len(feats)} polígonos | km2 {km2} -> {os.path.basename(out)}")

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ext = [AOI[0], AOI[2], AOI[1], AOI[3]]
        fig, ax = plt.subplots(1, 3, figsize=(16, 6))
        ax[0].imshow(np.where(np.isfinite(z0), z0, np.nan), extent=ext, cmap="terrain"); ax[0].set_title(f"{nombre} — DEM")
        ax[1].imshow(np.where(valido, twi, np.nan), extent=ext, cmap="Blues"); ax[1].set_title("TWI")
        cl = np.where(clase == 2, 2, np.where(clase == 1, 1, np.nan))
        ax[2].imshow(np.where(np.isfinite(z0), z0, np.nan), extent=ext, cmap="Greys_r", alpha=0.6)
        ax[2].imshow(cl, extent=ext, cmap="autumn_r", vmin=1, vmax=2, alpha=0.7); ax[2].set_title("Susceptibilidad")
        os.makedirs(SCRATCH, exist_ok=True)
        plt.tight_layout(); plt.savefig(os.path.join(SCRATCH, f"pluvial_{cid}.png"), dpi=105)
    except Exception as e:
        print("  PNG omitido:", e)
    return {cid: km2}


if __name__ == "__main__":
    pedidos = sys.argv[1:] or list(CIUDADES)
    resumen = {}
    for cid in pedidos:
        if cid not in CIUDADES:
            print("ciudad desconocida:", cid); continue
        nombre, aoi = CIUDADES[cid]
        r = procesar(cid, nombre, aoi)
        if r:
            resumen.update(r)
    print("\nRESUMEN km2:", json.dumps(resumen, ensure_ascii=False))
