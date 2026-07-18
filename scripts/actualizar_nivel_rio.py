"""
Descarga la COTA ACTUAL del río Paraguay desde la DINAC (Dirección de Meteorología
e Hidrología) y la guarda como JSON para la página de Situación actual.

Fuente oficial: https://www.meteorologia.gov.py/nivel-rio/indexconvencional.php
(datos actualizados a diario). Para actualizar el sitio: correr este script y
re-renderizar.

Salida: datos/nivel-rio-actual.json
"""
import os, re, json, urllib.request

URL = "https://www.meteorologia.gov.py/nivel-rio/indexconvencional.php"
# Estaciones del río Paraguay relevantes al proyecto (de norte a sur)
PY = ["Concepción", "Fuerte Olimpo", "Isla Margarita", "Asunción", "Villeta",
      "Alberdi", "Pilar"]
CRITICA_ASU = 5.5   # etapa crítica en Asunción (m), DMH / FloodList
OUT = os.path.join(os.path.dirname(__file__), "..", "datos", "nivel-rio-actual.json")

raw = urllib.request.urlopen(URL, timeout=40).read().decode("utf-8", errors="replace")
estaciones = []
for row in re.findall(r"<tr>(.*?)</tr>", raw, re.S):
    spans = [re.sub(r"<[^>]+>", "", s).strip() for s in re.findall(r"<span>(.*?)</span>", row, re.S)]
    if len(spans) < 3:
        continue
    nombre = spans[0]
    if nombre not in PY:
        continue
    mn = re.search(r"([-\d.]+)\s*m", spans[2])
    mc = re.search(r"([+-]?\d+)\s*cm", spans[3]) if len(spans) > 3 else None
    estaciones.append({"nombre": nombre, "fecha": spans[1],
                       "nivel_m": float(mn.group(1)) if mn else None,
                       "cambio_cm": int(mc.group(1)) if mc else None})
# ordenar norte->sur según PY
estaciones.sort(key=lambda e: PY.index(e["nombre"]))
fecha = next((e["fecha"] for e in estaciones if e["nombre"] == "Asunción"), "")
json.dump({"fuente": "DINAC (meteorologia.gov.py/nivel-rio)", "fecha": fecha,
           "critica_asuncion_m": CRITICA_ASU, "estaciones": estaciones},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"guardado ({len(estaciones)} estaciones, fecha {fecha}):")
for e in estaciones:
    print(f"  {e['nombre']}: {e['nivel_m']} m ({e['cambio_cm']:+d} cm)")
