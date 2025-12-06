# Análisis de Contratación Pública y Resultados Electorales en Colombia

Este proyecto implementa un flujo de trabajo de datos (ETL) y análisis econométrico para estudiar la relación entre los resultados electorales (específicamente márgenes de victoria y candidatos "outsiders") y los patrones de contratación pública en municipios de Colombia.

El análisis principal utiliza un Diseño de Regresión Discontinua (RDD) para estimar efectos causales en el uso de modalidades de contratación simplificada.

## Estructura del Proyecto

El proyecto sigue una estructura organizada por niveles de procesamiento de datos:

```
.
├── datasets/               # Almacenamiento de datos
│   ├── 01_raw/            # Datos crudos (Resultados electorales, SECOP I/II)
│   ├── 02_intermediate/   # Datos procesados y limpios individualmente
│   ├── 03_primary/        # Datos unificados (SECOP consolidado, Outsiders)
│   └── 04_mart/           # Base final lista para análisis (con controles)
├── scripts/                # Scripts de Python y R para ETL y análisis
├── stores/                 # Salidas del análisis (Gráficos PNG, Tablas LaTeX)
├── requirements.txt        # Dependencias de Python
└── README.md               # Documentación del proyecto
```

## Fuentes de Datos

El proyecto se alimenta de dos fuentes principales de información pública colombiana:

1.  **Resultados Electorales (2019):**
    *   **Origen:** Registraduría Nacional del Estado Civil.
    *   **Contenido:** Resultados detallados mesa a mesa o agregados por municipio para las elecciones de autoridades locales (Alcaldes).
    *   **Ubicación:** `datasets/01_raw/resultados_*_2019.csv`.

2.  **Contratación Pública (SECOP I y II):**
    *   **Origen:** Portal de Datos Abiertos del Estado Colombiano (Colombia Compra Eficiente).
    *   **Contenido:** Registros históricos de procesos de contratación estatal.
    *   **Ubicación:** `datasets/01_raw/secop*.csv`.

## Proceso de Limpieza y Transformación

El pipeline de datos realiza una limpieza exhaustiva para asegurar la calidad del análisis econométrico.

### 1. Procesamiento Electoral (`scripts/process_resultados_alcaldias.py` y `outsiders.py`)
*   **Filtrado:** Se seleccionan exclusivamente las elecciones para **Alcaldía**.
*   **Depuración:** Se eliminan votos nulos, no marcados y en blanco.
*   **Clasificación de Partidos:** Se define una lista de partidos "Tradicionales" (ej. Liberal, Conservador, Centro Democrático, Cambio Radical, La U, etc.). Cualquier partido o movimiento no incluido en esta lista se clasifica como **"Outsider"**.
*   **Cálculo de Margen de Victoria:**
    *   Se identifican los dos candidatos con más votos en cada municipio (Top 2).
    *   Se filtra para mantener solo municipios "mixtos" (donde compite un Outsider vs. un Tradicional).
    *   **Variable de Ejecución (Running Variable):** Margen de victoria = (Votos Outsider - Votos Tradicional) / (Total Votos Top 2).

### 2. Procesamiento de Contratación (`scripts/secop.py`)
*   **Unificación:** Se concatenan y homologan los esquemas de **SECOP I** y **SECOP II**.
*   **Filtros de Calidad:**
    *   **Temporal:** Se conservan adjudicaciones entre **2015 y 2023**.
    *   **Institucional:** Se filtra por entidades que contengan "Alcaldía" o "Municipio" en su nombre.
    *   **Validez:** Se eliminan contratos sin valor (0), sin NIT de entidad, o no adjudicados.
*   **Clasificación de Modalidades:** Se crea una variable binaria `simplificada` que agrupa:
    *   Contratación Directa.
    *   Mínima Cuantía.
    *   Selección Abreviada de Menor Cuantía.
    *   Régimen Especial.
    *   *Excluye:* Licitaciones públicas, subastas inversas, concursos de méritos.
*   **Recuperación Geográfica:** Se implementa un algoritmo de búsqueda de texto para imputar el municipio correcto en registros donde el campo ciudad aparece como "No Definido", utilizando el nombre de la entidad contratante.

### 3. Construcción de la Base Final (`scripts/final_database.py`)
*   **Cruce de Información:** Se realiza un *inner join* entre la base electoral (Outsiders) y la base de contratación (SECOP) utilizando nombres normalizados de municipio y departamento (sin tildes, minúsculas).
*   **Definición de Periodos:**
    *   **Periodo de Análisis (Variable Dependiente):** 2020-2023 (Mandato del alcalde electo en 2019).
    *   **Periodo de Control (Covariables):** 2015 - Septiembre 2019 (Histórico previo para pruebas de balance).
*   **Variables Calculadas:**
    *   `pct_simplif_count`: Porcentaje de contratos adjudicados vía modalidad simplificada (en cantidad).
    *   `pct_simplif_value`: Porcentaje del valor total adjudicado vía modalidad simplificada.
    *   `HHI`: Índice Herfindahl-Hirschman de concentración de contratistas.

## Análisis Econométrico (R)

El script `scripts/01_rdd_analysis.R` ejecuta el diseño RDD:

1.  **Estimación:** Regresiones polinómicas locales (`rdrobust`) para estimar el salto en la contratación simplificada en el umbral donde gana un Outsider (margen = 0).
2.  **Robustez:**
    *   Variación de anchos de banda (Óptimo MSE, 0.5x, 2.0x).
    *   Inclusión de polinomios de grado 1 y 2.
    *   Control por covariables históricas (contratación pasada).
3.  **Validación:**
    *   **Test de McCrary:** Verifica que no haya manipulación en la densidad de elecciones alrededor del umbral de victoria.
    *   **Pruebas de Placebo:** Verifica que no existan discontinuidades en variables pre-determinadas (ej. número de contratos o valor contratado en el periodo anterior).

## Requisitos de Instalación

### Python
```bash
pip install -r requirements.txt
```

### R
Paquetes necesarios:
- `tidyverse`
- `rdrobust`
- `rddensity`
- `stargazer`

## Resultados

Los resultados gráficos y tablas se generan automáticamente en la carpeta `stores/`.
- **Tablas:** `rdd_results_pct_simplif_count.tex`
- **Gráficos:** `rdd_plot_*.png`

## Autores
Proyecto realizado para el curso de Econometría Avanzada - PEG Uniandes.
