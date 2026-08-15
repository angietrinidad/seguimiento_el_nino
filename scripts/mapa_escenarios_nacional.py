"""
Mapa nacional de afectación por escenario de crecida (río Paraguay/Paraná).

Muestra los DEPARTAMENTOS con afectación registrada oficialmente en los episodios
análogos y las CIUDADES ribereñas que se inundan (el conteo por ciudad solo existe
completo para 2024; para 2015-16 y 2019 la afectación oficial es por departamento).

Fuentes de la afectación departamental:
- Severo (2019): 9 deptos, SEN vía prensa (eldiario/EFE) + Shelter Projects.
- Extremo (2015-16): emergencia Ley 5561 en 7 deptos (IFRC MDRPY018).
Ciudades ribereñas: corredor documentado de los ríos Paraguay y Paraná.

Salida: datos/geo/mapa-escenarios-nacional.png  (validar visualmente antes de publicar)
"""
import os, json, unicodedata
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

BASE = os.path.dirname(__file__)
GEO = os.path.join(BASE, "..", "datos", "geo")

def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()

# Departamentos afectados por episodio (norm)
SEVERO = {"PRESIDENTE HAYES", "CENTRAL", "SAN PEDRO", "CONCEPCION", "CORDILLERA",
          "CAPITAL", "NEEMBUCU", "BOQUERON", "ALTO PARAGUAY"}                    # 2019, SEN
EXTREMO = {"CONCEPCION", "SAN PEDRO", "MISIONES", "NEEMBUCU", "AMAMBAY",
           "PRESIDENTE HAYES", "CENTRAL", "CAPITAL"}                            # 2015-16, Ley 5561 (+Capital)

# Ciudades ribereñas (corredor de los ríos Paraguay y Paraná) — lon, lat
CIUDADES = [
    ("Bahía Negra",   -58.17, -20.23),
    ("Fuerte Olimpo", -57.87, -21.04),
    ("Concepción",    -57.43, -23.40),
    ("Villa Hayes",   -57.52, -25.10),
    ("Asunción",      -57.64, -25.30),
    ("Villeta",       -57.55, -25.51),
    ("Alberdi",       -58.14, -26.24),
    ("Pilar",         -58.30, -26.86),
    ("Ayolas",        -56.90, -27.40),
    ("Encarnación",   -55.87, -27.33),
]

deps = gpd.read_file(os.path.join(GEO, "departamentos-py.geojson"))
deps["N"] = deps["shapeName"].map(norm)

def color(n):
    en_s, en_e = n in SEVERO, n in EXTREMO
    if en_s and en_e: return "#8c2d3f"   # ambos
    if en_s:          return "#c96a4a"   # solo severo (2019)
    if en_e:          return "#d9a441"   # solo extremo (2015-16)
    return "#eceae6"                      # sin afectación registrada

fig, ax = plt.subplots(figsize=(7.2, 9.4), dpi=140)
deps.plot(ax=ax, color=[color(n) for n in deps["N"]], edgecolor="white", linewidth=0.6)

# ciudades
for nombre, lon, lat in CIUDADES:
    ax.plot(lon, lat, "o", color="#141414", markersize=4, zorder=5)
    dx = 0.12
    ha = "left"
    ax.annotate(nombre, (lon, lat), xytext=(lon + dx, lat), fontsize=8.5,
                ha=ha, va="center", zorder=6,
                fontweight="bold", color="#141414")

ax.set_axis_off()
ax.set_title("Afectación por crecida a escala nacional\ndepartamentos con emergencia declarada + ciudades ribereñas",
             fontsize=12, fontweight="bold", color="#141414", loc="left")

leg = [
    Patch(facecolor="#8c2d3f", label="Afectado en severo (2019) y extremo (2015-16)"),
    Patch(facecolor="#c96a4a", label="Severo — crecida 2019 (SEN, 9 deptos)"),
    Patch(facecolor="#d9a441", label="Extremo — El Niño 2015-16 (emergencia, 7 deptos)"),
    Patch(facecolor="#eceae6", label="Sin afectación registrada en estos episodios"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor="#141414",
           markersize=6, label="Ciudad ribereña que se inunda"),
]
ax.legend(handles=leg, loc="lower left", fontsize=7.8, frameon=True,
          facecolor="white", edgecolor="#ccc", framealpha=0.95)
ax.text(0.0, -0.02,
        "Fuentes: SEN vía prensa (2019); IFRC/Cruz Roja MDRPY018 (2015-16). "
        "El conteo por ciudad solo existe completo para 2024 (sur).",
        transform=ax.transAxes, fontsize=6.8, color="#6B6763", va="top")

plt.tight_layout()
out = os.path.join(GEO, "mapa-escenarios-nacional.png")
plt.savefig(out, bbox_inches="tight", facecolor="white")
print("OK ->", out)
