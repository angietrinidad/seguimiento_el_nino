# Desastres Anunciados

Base empírica y documental sobre el **riesgo de desastres en Paraguay** desde una
mirada crítica: los desastres **no son naturales** —se construyen socialmente
(riesgo = amenaza × vulnerabilidad)— y **casi nunca son sorpresa**: el clima se
pronostica y la vulnerabilidad se conoce, así que el desastre llega **anunciado**. Cubre varias **amenazas** —inundación fluvial y pluvial,
sequía y bajante, olas de frío, dengue e incendios— y su **exposición** (población,
salud, educación, actividad comercial, agricultura y ganadería). Base para
investigación en sociología y gestión del riesgo de desastres.

## Estructura

```
├── index.qmd                  Panel de control (KPIs en vivo + grilla de amenazas)
├── marco/                     El desastre como construcción social + ENOS
├── amenazas/                  Un módulo por amenaza (plantilla común)
│   ├── inundacion-fluvial/    Desborde del río (huellas Sentinel-1)
│   ├── inundacion-pluvial/    Lluvia (escala, IDF, DEM multiciudad, eventos)
│   ├── sequia/  frio/  dengue/  incendios/
├── exposicion/                Población, salud, educación y comercio (mapa)
├── agro-ganaderia/            Agricultura y ganadería como medios de vida (uso del suelo)
├── situacion-actual/          Monitoreo en vivo (río + lluvia DMH) del episodio ENOS
├── recomendaciones/           Acción anticipatoria por amenaza (SEN + normas HSP)
├── contexto-america-latina/ contexto-paraguay/ contexto-asuncion/   Contexto histórico ENOS
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
