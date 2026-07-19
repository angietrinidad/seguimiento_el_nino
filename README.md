# Desastres Construidos

Base empírica y documental sobre el **riesgo de desastres en Paraguay** desde una
mirada crítica: **el desastre no es natural, se construye socialmente** (riesgo =
amenaza × vulnerabilidad). Cubre varias **amenazas** —inundación fluvial y pluvial,
sequía y bajante, olas de frío, dengue e incendios— y su **exposición** (población,
salud, educación, actividad comercial, agricultura y ganadería). Base para
investigación en sociología y gestión del riesgo de desastres.

## Estructura

```
├── index.qmd                  Panel de control (KPIs en vivo + grilla de amenazas)
├── 01-marco-conceptual/       Marco: el desastre como construcción social + ENOS
├── amenazas/                  Módulos por amenaza (plantilla común)
│   ├── sequia/  frio/  dengue/  incendios/
├── 05-mapa-riesgo/            Inundación fluvial (huellas Sentinel-1)
├── 08-pluvial/                Inundación pluvial (escala, IDF, DEM, eventos)
├── 06-exposicion/             Exposición: población, salud, educación, comercio (mapa)
├── agro-ganaderia/            Agricultura y ganadería como medios de vida
├── situacion-actual/          Monitoreo en vivo (río + lluvia DMH) del episodio ENOS
├── 07-recomendaciones/        Acción anticipatoria (SEN + normas HSP)
├── 02-america-latina/ 03-paraguay/ 04-asuncion-metropolitana/   Contexto histórico ENOS
├── scripts/                   Procesamiento (Sentinel-1, DEM, OSM, Overpass, DMH)
├── datos/                     Series CSV, GeoJSON derivados, Excels de exposición
├── referencias.bib            Bibliografía (APA 7) — ~150 fuentes verificadas
└── metodologia.qmd            Convenciones y reglas del repositorio
```

## Principios

- Prioridad a **fuentes oficiales y datos primarios**.
- **No se fabrican cifras**: todo número tiene fuente verificable; las
  estimaciones no confirmadas se marcan como tales.
- Los **vacíos de información** se señalan de forma explícita (clase `.vacio`).
- Lente crítico atento al **género, la clase y la desigualdad territorial**.

## Cómo construir el sitio

Requiere [Quarto](https://quarto.org/docs/get-started/) y Python 3.

```bash
pip install -r requirements.txt
quarto preview      # vista local con recarga
quarto render       # genera el sitio en _site/
```

## Publicación

El sitio se publica en GitHub Pages. Opción recomendada:

```bash
quarto publish gh-pages
```

## Licencia

Contenido documental de uso académico. Ver fuentes originales para condiciones
de reutilización de cada dato.
