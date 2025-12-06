# ============================================================
# 00_Config.R - Configuración base para todo el proyecto
# ============================================================

# Limpiar entorno
rm(list = ls())

# Lista de paquetes requeridos para el análisis completo
# instalar pacman
if(!require(pacman)) install.packages("pacman") ; require(pacman)

p_load(
  tidyverse,      # Manipulación y visualización de datos
  haven,          # Importar archivos de Stata, SPSS, SAS
  data.table,     # Manipulación eficiente de datos
  stargazer,      # Tablas de regresión
  ggplot2,        # Visualización avanzada
  dplyr,          # Manipulación de datos
  readr,          # Lectura de archivos
  knitr,          # Generación de reportes
  kableExtra,     # Tablas mejoradas
  here,           # Manejo de rutas
  fixest,         # Modelos de efectos fijos
  modelsummary,   # Tablas de modelos (mejor integración con fixest)
  bacondecomp,
  broom,
  did,
  Synth,
  lubridate,
  gridExtra,
  rdrobust,       # Regresión Discontinua Robusta
  rddensity       # Test de Densidad de McCrary
)
# Definir rutas 
# Identificamos la ruta del script actual
script_path <- rstudioapi::getSourceEditorContext()$path
script_dir  <- dirname(script_path)

# Creamos carpeta stores (si no existe) en la raíz del proyecto
stores_path <- file.path(dirname(script_dir), "stores")
if (!dir.exists(stores_path)) {
  dir.create(stores_path, recursive = TRUE)
}

# Función de ayuda para construir rutas hacia stores
store_file <- function(filename) {
  file.path(stores_path, filename)
}