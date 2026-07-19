# CLAUDE.md — guía para trabajar en este repositorio

Sitio **"Desastres Anunciados"**: base empírica y documental sobre el **riesgo de
desastres en Paraguay** desde una mirada crítica. Tesis doble: el desastre **no es
natural** (se construye socialmente: riesgo = amenaza × vulnerabilidad) y está
**anunciado** (el clima se pronostica, la vulnerabilidad se conoce). Uso: investigación
en sociología y gestión del riesgo de desastres (enfoque feminista-decolonial).

Repo **privado**; sitio alojado en **Netlify** con dominio propio:
<https://desastresanunciados.org>

## Regla dura (innegociable) — ver `CONTEXTO.md`
**No fabricar cifras.** Todo número debe tener fuente verificable (URL/DOI). Lo no
confirmado se marca `s/d`; los vacíos de información se señalan con la clase `.vacio`.
Priorizar fuentes oficiales y primarias. Antes de publicar cualquier análisis derivado
(Sentinel-1, DEM, WorldCover), **validar con un PNG**.

## Stack y flujo de trabajo
- **Quarto** (sitio web) + Python 3.11. En Windows, Python se invoca con **`py`** (no
  `python`). Quarto: `& "$env:LOCALAPPDATA\Programs\Quarto\bin\quarto.cmd"` (no está en PATH).
- **Render:** `quarto render` (proyecto completo; `execute-dir: project`, rutas a
  `datos/` relativas a la raíz). Freeze `auto`.
- **Publicar:** `quarto publish netlify` (renderiza en local y sube el `_site` a
  Netlify; token cacheado tras la 1ª autorización). Antes se usaba `gh-pages`.
- **Commit/push a `main`** (repo privado) con cada cambio; luego publicar.
- Tras cada render puede aparecer `_quarto_internal_scss_error.scss` — es un **quirk no
  fatal** del tema cosmo; borrarlo y seguir (el sitio renderiza bien).

## Estructura (nombres semánticos; reorganizado 2026-07-19)
```
index.qmd                     Panel de control (KPIs en vivo + grilla de amenazas)
marco/                        El desastre como construcción social + ENOS
amenazas/                     Hub + 6 módulos (plantilla común)
  inundacion-fluvial/  inundacion-pluvial/  sequia/  frio/  dengue/  incendios/
exposicion/                   Población, salud, educación, comercio (mapa + Excels)
agro-ganaderia/               Agricultura y ganadería + mapa de uso del suelo
situacion-actual/             Monitoreo en vivo (río DINAC + lluvia DMH)
recomendaciones/              Acción anticipatoria por amenaza (SEN + HSP)
contexto-america-latina/  contexto-paraguay/  contexto-asuncion/   Contexto histórico ENOS
scripts/  datos/  referencias.bib  metodologia.qmd  fuentes/
```
Las URLs viejas (`/05-mapa-riesgo/`, etc.) **redirigen** vía `aliases` + el hook
`scripts/fix_redirects.py` (`post-render` en `_quarto.yml`).

## Gotchas específicos
- En bloques `.qmd`, un `Markdown(...)`/`HTML(...)` dentro de `if/else` **no se
  auto-muestra**; asignar a variable y llamar `HTML(var)` a nivel superior.
- Los **grupos de cita** `[@a; @b]` **fallan dentro de `.callout`/`.vacio`** (salen
  literales); usar cita única ahí. En párrafos/listas normales los grupos funcionan.
- Anclas de Quarto **conservan acentos** (`#una-escala-empírica-…`).
- Datos geoespaciales: DEM y WorldCover vía Microsoft Planetary Computer (a veces da
  504 → reintentar). OSM vía Overpass (User-Agent propio; probar varios mirrors).
  Estaciones DMH: feed `meteorologia.gov.py/emas/data.json` (SSL sin verificar).

## Estado (qué está hecho)
6 amenazas con módulo + acción anticipatoria; exposición (mapa con salud/educación/
comercio + Excels de escuelas/salud/comercio); agro-ganadería con uso del suelo
(WorldCover); panel de control con KPIs en vivo; situación actual con río y lluvia en
vivo; ~150 referencias verificadas. Susceptibilidad pluvial (DEM) para 5 ciudades.

## Pendientes / próximos pasos
- Poblar **dengue** con más profundidad si se requiere (ya tiene base sólida).
- **Agricultura familiar**: series recientes por rubro (mandioca, poroto, sésamo) por
  departamento; caña de azúcar 2024-25 — sin fuente única aún (`s/d`).
- Posible **choropleth departamental** de ganado/cultivos (falta dato por depto).
- Actualizar datos en vivo periódicamente: `scripts/actualizar_nivel_rio.py`,
  `scripts/estaciones_dmh.py`.

## Memoria
Hay memoria persistente del proyecto en
`~/.claude/projects/.../memory/proyecto-seguimiento-el-nino.md` (detalle técnico fino:
metodología Sentinel-1, endpoints MEC/MSPBS, decisiones no obvias). Mantenerla al día.
