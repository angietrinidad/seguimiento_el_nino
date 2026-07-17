# Seguimiento El Niño (ENOS)

Repositorio documental sobre el fenómeno **El Niño-Oscilación del Sur (ENOS)**
con tres niveles de resolución geográfica —**América Latina**, **Paraguay**
(nacional y departamental) y **Asunción y área metropolitana**— como base
empírica para investigación en sociología y gestión del riesgo de desastres.

## Estructura

```
├── index.qmd                     Portada + tabla resumen comparativa
├── 01-marco-conceptual/          ENOS: definición y mecanismos físicos
├── 02-america-latina/            Panorama regional e institucional
├── 03-paraguay/
│   ├── nacional.qmd
│   └── departamentos/
├── 04-asuncion-metropolitana/    Hidrología, DGRRD, vulnerabilidad urbana
├── datos/                        Series de tiempo en CSV + diccionario
├── fuentes/                      Registro y priorización de fuentes
├── referencias.bib               Bibliografía (APA 7)
└── metodologia.qmd               Convenciones y reglas del repositorio
```

## Principios

- Prioridad a **fuentes oficiales y datos primarios**.
- **No se fabrican cifras**: todo número tiene fuente verificable; las
  estimaciones no confirmadas se marcan como tales.
- Los **vacíos de información** se señalan de forma explícita.
- Foco en el episodio **2026-2027** en curso, con valor comparativo de
  1997-98, 2015-16 y 2023-24.

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
