# Proyecto de Extracción de Datos - Econometría Avanzada

Este proyecto contiene scripts para extraer datos de diferentes fuentes relacionadas con contratación pública y resultados electorales en Colombia.

## 📋 Requisitos

### Instalación de dependencias

```bash
pip install -r requirements.txt
```

### Instalación adicional para Playwright

Después de instalar los paquetes, es necesario instalar los navegadores de Playwright:

```bash
python -m playwright install chromium
```

## 📂 Estructura del proyecto

```
final-paper/
├── datasets/
│   ├── 01_raw/                                # Datos crudos sin procesar
│   │   ├── secop_contratacion.csv             # Base de datos SECOP contratación
│   │   ├── secop_proponentes.csv              # Base de datos SECOP proponentes
│   │   └── resultados_{departamento}_{año}.csv # Resultados electorales por depto/año
│   └── 02_intermediate/                       # Datos procesados intermedios
│       ├── resultados_electorales_intermediate.csv # Top 2 candidatos por municipio
│       └── alcaldes_ganadores_2015.csv        # Alcaldes ganadores 2015
├── scripts/
│   ├── extract_secop_contratacion.py      # Extrae datos de contratación
│   ├── extract_secop_proponentes.py       # Extrae datos de proponentes
│   ├── extract_resultados_electorales.py  # Extrae resultados electorales
│   ├── extract_alcaldes_2015.py           # Extrae alcaldes ganadores 2015 (Wikipedia)
│   └── process_resultados_alcaldias.py    # Procesa resultados de alcaldías
└── requirements.txt
```

## 🚀 Scripts disponibles

### 1. Extracción de datos SECOP - Contratación

Extrae datos de contratación pública desde la API de datos abiertos de Colombia:

```bash
python scripts/extract_secop_contratacion.py
```

- **Fuente**: https://www.datos.gov.co/resource/p6dx-8zbt.json
- **Salida**: `datasets/01_raw/secop_contratacion.csv`
- **Características**:
  - ~8M de registros
  - Paginación automática (lotes de 50,000)
  - Guarda chunks intermedios cada 100,000 registros
  - Elimina chunks automáticamente al finalizar

### 2. Extracción de datos SECOP - Proponentes

Extrae datos de proponentes/proveedores en procesos de contratación:

```bash
python scripts/extract_secop_proponentes.py
```

- **Fuente**: https://www.datos.gov.co/resource/hgi6-6wh3.json
- **Salida**: `datasets/01_raw/secop_proponentes.csv`
- **Características**:
  - Paginación automática
  - Incluye NIT y códigos de proveedores
  - Sistema de chunks para seguridad

### 3. Extracción de resultados electorales

Descarga resultados electorales por departamento usando web scraping:

```bash
python scripts/extract_resultados_electorales.py
```

- **Fuente**: Registraduría Nacional del Estado Civil
- **Salida**: `datasets/01_raw/resultados_{departamento}_{año}.csv`
- **Años**: 2019, 2023
- **Características**:
  - Web scraping con Playwright + descarga directa con requests
  - Descarga archivos ZIP, extrae CSV automáticamente
  - Formato estandarizado: `resultados_departamento_año.csv`
  - Detección automática de selectores según el año
  - Barra de progreso de descarga
  - Limpieza automática de archivos ZIP después de extracción
  - Skip automático de archivos ya descargados

### 4. Procesamiento de resultados de alcaldías

Procesa los resultados electorales para obtener los top 2 candidatos por municipio:

```bash
python scripts/process_resultados_alcaldias.py
```

- **Entrada**: `datasets/01_raw/resultados_*_2019.csv`
- **Salida**: `datasets/02_intermediate/resultados_electorales_intermediate.csv`
- **Características**:
  - Filtra solo resultados de alcaldías
  - Excluye votos no marcados, en blanco y nulos
  - Agrupa y suma votos por candidato en cada municipio
  - Extrae top 2 candidatos con más votos por municipio
  - Consolida todos los departamentos en un solo archivo
  - Incluye información de departamento, municipio, candidato y partido

### 5. Extracción de alcaldes ganadores 2015

Extrae información de alcaldes ganadores en 2015 desde Wikipedia:

```bash
python scripts/extract_alcaldes_2015.py
```

- **Fuente**: Wikipedia - Elecciones regionales de Colombia de 2015
- **Salida**: `datasets/02_intermediate/alcaldes_ganadores_2015.csv`
- **Características**:
  - Web scraping con BeautifulSoup
  - Extrae alcaldes ganadores por municipio
  - Incluye departamento, municipio, candidato ganador y partido
  - Datos consolidados de todo el país

## 📊 Información de los datasets

### SECOP Contratación
Incluye información sobre:
- Entidad contratante
- Proceso de contratación
- Modalidad y tipo de contrato
- Valores y fechas
- Estado del proceso
- Proveedor adjudicado

### SECOP Proponentes
Incluye información sobre:
- ID del procedimiento
- Fecha de publicación
- Entidad compradora
- Proveedor/Proponente
- NITs y códigos

### Resultados Electorales (Raw)
Incluye información sobre:
- Resultados por departamento y municipio
- Datos de elecciones 2019 y 2023
- Votos por mesa, candidato y corporación
- Información electoral detallada

### Resultados Electorales (Intermediate)
Dataset procesado con:
- Top 2 candidatos con más votos por municipio
- Solo elecciones de alcaldía (2019)
- Votos válidos (excluye blancos, nulos y no marcados)
- Datos consolidados de todos los departamentos
- Información de candidato, partido y municipio

### Alcaldes Ganadores 2015
Dataset extraído de Wikipedia con:
- Alcaldes ganadores por municipio (2015)
- Departamento y municipio
- Nombre del candidato ganador
- Partido político del ganador
- Datos de todo el país

## ⚙️ Configuración

### Cambiar años de resultados electorales

Edita la variable `YEARS` en `scripts/extract_resultados_electorales.py`:

```python
YEARS = ["2019", "2023"]  # Agregar o quitar años según necesidad
```

### Ajustar tamaño de lotes SECOP

En los scripts de SECOP, ajusta `batch_size` en la clase extractora:

```python
self.batch_size = 50000  # Máximo recomendado por Socrata
```

## 🔧 Solución de problemas

### Error de Playwright
Si obtienes un error relacionado con Playwright:
```bash
python -m playwright install chromium
```

### Error de timeout en descargas
Ajusta el parámetro en el script:
```python
main(headless=True, pause_between_downloads_sec=1.5)  # Aumentar el delay
```

### Memoria insuficiente
Los scripts guardan chunks intermedios automáticamente para evitar problemas de memoria.

## 📝 Notas

- Los scripts muestran progreso en tiempo real con barras de progreso (tqdm)
- Todos los logs incluyen timestamps para facilitar el debugging
- Los archivos intermedios se eliminan automáticamente al finalizar
- Las carpetas de salida se crean automáticamente si no existen

## 🤝 Contribuciones

Este proyecto es parte del trabajo final del curso de Econometría Avanzada - PEG Uniandes.

