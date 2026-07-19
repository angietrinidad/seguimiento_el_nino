"""
Estaciones Meteorológicas Automáticas (EMAs) de la DMH/DINAC — cobertura NACIONAL.

Feed oficial en tiempo real: https://www.meteorologia.gov.py/emas/data.json
(se actualiza ~cada 3 min). La DMH publica la precipitación de las automáticas como
ACUMULADO DEL DÍA en hora local (medición cada 10 min UTC); es "orientativa, no
oficial" según la propia DMH.

Salida: datos/estaciones-dmh-metro.json
- actualizado (utc/local del feed)
- estaciones (todas las del país): nombre, ciudad, departamento, lat, lon, altura,
  activa (transmite <=3 h), metro (Asunción+Central), prioritario (depto ribereño),
  ultima_obs (local), precip_dia_mm (acumulado del día según DMH)

Uso: monitoreo pluvial en vivo (situación actual, nacional + metro) y referencia de
qué estaciones pedir a la DMH para reconstruir la serie histórica / curvas IDF.
"""
import os, json, ssl, urllib.request
from datetime import datetime

URL = "https://www.meteorologia.gov.py/emas/data.json"
OUT = os.path.join(os.path.dirname(__file__), "..", "datos", "estaciones-dmh-metro.json")
METRO = {"Asunción", "Asuncion", "Central"}
# Departamentos ribereños/agrícolas prioritarios del repositorio
PRIORITARIOS = {"Asunción", "Asuncion", "Central", "Concepción", "Concepcion",
                "San Pedro", "Presidente Hayes", "Pdte. Hayes", "Ñeembucú", "Neembucu",
                "Misiones", "Itapúa", "Itapua", "Alto Paraná", "Alto Parana"}

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
    o = e.get("ultima_observacion") or {}
    obs_local = val(o, "fecha", "local")
    atraso_h = horas_desde(obs_local, ref_local) if obs_local else None
    dep = m.get("departamento")
    estaciones.append({
        "id": m.get("id"),
        "nombre": m.get("nombre"),
        "ciudad": m.get("ciudad"),
        "departamento": dep,
        "lat": m.get("latitud"), "lon": m.get("longitud"), "altura_m": m.get("altura"),
        # activa = transmitió en las últimas ~3 horas
        "activa": atraso_h is not None and atraso_h <= 3,
        "atraso_horas": atraso_h,
        "metro": dep in METRO,
        "prioritario": dep in PRIORITARIOS,
        "ultima_obs_local": obs_local,
        "precip_dia_mm": val(o, "precipitacion", "valor"),
        "temp_c": val(o, "temperatura_aire", "valor"),
    })

# orden: activas primero, luego por departamento y ciudad
estaciones.sort(key=lambda s: (not s["activa"], s["departamento"] or "", s["ciudad"] or ""))
activas = [s for s in estaciones if s["activa"]]
out = {"fuente": "DMH/DINAC — EMAs (data.json)", "url": URL,
       "nota": "Precipitación = acumulado del día en hora local (DMH); orientativa, no oficial.",
       "actualizado": d.get("actualizado"),
       "resumen": {"total": len(estaciones), "activas": len(activas),
                   "activas_prioritarias": len([s for s in activas if s["prioritario"]])},
       "estaciones": estaciones}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"estaciones nacionales: {len(estaciones)} | activas: {len(activas)} "
      f"| activas en deptos prioritarios: {out['resumen']['activas_prioritarias']}")
for s in activas:
    flag = "P" if s["prioritario"] else " "
    print(f"  [{flag}] {(s['departamento'] or '')[:14]:14s} {(s['ciudad'] or '')[:14]:14s} "
          f"{(s['nombre'] or '')[:34]:34s} | {s['precip_dia_mm']} mm")
