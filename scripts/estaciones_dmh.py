"""
Estaciones Meteorológicas Automáticas (EMAs) de la DMH/DINAC — subconjunto del
área metropolitana de Asunción (departamentos Asunción y Central).

Feed oficial en tiempo real: https://www.meteorologia.gov.py/emas/data.json
(se actualiza ~cada 3 min). La DMH publica la precipitación de las automáticas como
ACUMULADO DEL DÍA en hora local (medición cada 10 min UTC); es "orientativa, no
oficial" según la propia DMH.

Salida: datos/estaciones-dmh-metro.json
- actualizado (utc/local del feed)
- estaciones: nombre, ciudad, departamento, lat, lon, altura, activa (transmite),
  ultima_obs (local), precip_mm (acumulado del día según DMH)

Uso: monitoreo pluvial en vivo (situación actual) y referencia de qué estaciones
pedir a la DMH para reconstruir la serie histórica / curvas IDF de Asunción.
"""
import os, json, ssl, urllib.request
from datetime import datetime

URL = "https://www.meteorologia.gov.py/emas/data.json"
OUT = os.path.join(os.path.dirname(__file__), "..", "datos", "estaciones-dmh-metro.json")
DEPTOS = {"Asunción", "Asuncion", "Central"}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE  # el certificado de la DMH no valida en algunos entornos
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
d = json.loads(urllib.request.urlopen(req, timeout=45, context=ctx).read().decode("utf-8", "replace"))

def val(o, *ks):
    for k in ks:
        o = (o or {}).get(k)
    return o

def horas_desde(ts, ref):
    try:
        return round((datetime.fromisoformat(ref) - datetime.fromisoformat(ts)).total_seconds() / 3600, 1)
    except Exception:
        return None

ref_local = val(d, "actualizado", "local")
estaciones = []
for e in d.get("estaciones", {}).values():
    m = e.get("metadatos", {})
    if m.get("departamento") not in DEPTOS:
        continue
    o = e.get("ultima_observacion") or {}
    obs_local = val(o, "fecha", "local")
    atraso_h = horas_desde(obs_local, ref_local) if obs_local else None
    estaciones.append({
        "id": m.get("id"),
        "nombre": m.get("nombre"),
        "ciudad": m.get("ciudad"),
        "departamento": m.get("departamento"),
        "lat": m.get("latitud"), "lon": m.get("longitud"), "altura_m": m.get("altura"),
        # activa = transmitió en las últimas ~3 horas
        "activa": atraso_h is not None and atraso_h <= 3,
        "atraso_horas": atraso_h,
        "ultima_obs_local": obs_local,
        "precip_dia_mm": val(o, "precipitacion", "valor"),
        "temp_c": val(o, "temperatura_aire", "valor"),
    })

# orden: activas primero, luego por ciudad
estaciones.sort(key=lambda s: (not s["activa"], s["ciudad"] or ""))
out = {"fuente": "DMH/DINAC — EMAs (data.json)", "url": URL,
       "nota": "Precipitación = acumulado del día en hora local (DMH); orientativa, no oficial.",
       "actualizado": d.get("actualizado"), "estaciones": estaciones}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

activas = [s for s in estaciones if s["activa"]]
print(f"estaciones metro (Asunción+Central): {len(estaciones)} | activas: {len(activas)}")
for s in estaciones:
    flag = "*" if s["activa"] else "-"
    print(f"  {flag} {s['ciudad']:14s} {(s['nombre'] or '')[:40]:40s} | {s['ultima_obs_local']} | {s['precip_dia_mm']} mm")
