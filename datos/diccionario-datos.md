# Diccionario de datos

Todos los archivos `.csv` de esta carpeta siguen convenciones comunes para
garantizar trazabilidad (ver skill de trazabilidad de fuente única) y cumplir
la restricción del proyecto: **no fabricar cifras**.

## Columnas transversales

| Columna | Descripción |
|---|---|
| `fuente` | Identificador corto de la fuente (ver `fuentes/registro.csv`) |
| `confiabilidad` | `oficial` \| `academico` \| `prensa` \| `estimacion` |
| `fecha_publicacion` | Fecha del documento fuente (AAAA-MM-DD) |
| `variable` | Variable medida (precipitacion, temperatura, nivel_rio, poblacion_afectada, sector_economico) |

## Convención para vacíos

- Celda **vacía** = dato aún no recolectado.
- Valor `s/d` = la fuente existe pero no reporta el dato (sin dato).
- Valor `NC` = estimación **no confirmada** (debe ir acompañada de nota).

Nunca se rellena una celda con un número sin fuente verificable.

## Archivos

| Archivo | Contenido |
|---|---|
| `episodios.csv` | Clasificación de intensidad de cada episodio El Niño (base ONI de NOAA) |
| `paraguay-series.csv` | Series de tiempo por episodio y variable a nivel Paraguay |
| `nivel-rio-paraguay.csv` | Nivel del río Paraguay en Asunción por episodio |
| `poblacion-afectada.csv` | Población / familias afectadas o desplazadas por episodio y nivel |

### `intensidad_oni` (episodios.csv)

Clasificación estándar del Oceanic Niño Index (ONI) de NOAA/CPC según el pico
de anomalía en la región Niño 3.4:

| Categoría | Umbral ONI (°C) |
|---|---|
| débil | 0.5 a 0.9 |
| moderado | 1.0 a 1.4 |
| fuerte | 1.5 a 1.9 |
| muy fuerte | ≥ 2.0 |
