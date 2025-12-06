# 1. Configuración inicial
# Asumimos que el directorio de trabajo es la raíz del proyecto
if (file.exists("scripts/00_config.R")) {
  source("scripts/00_config.R")
} else {
  # Si se corre desde la carpeta scripts
  source("00_config.R")
}

# 2. Importar la base de datos
# Ajusta la ruta si es necesario, asumiendo que el script corre desde la raíz del proyecto o la carpeta scripts
data_path <- "datasets/04_mart/final_database.csv"
if (!file.exists(data_path)) {
  # Intentar ruta relativa si se corre desde la carpeta scripts
  data_path <- "../datasets/04_mart/final_database.csv"
}

df <- read_csv(data_path)

# Limpieza básica y manejo de missings si es necesario para las variables de interés
# HHI y margen_victoria no deben ser NA
df_rdd <- df %>%
  filter(!is.na(HHI), !is.na(margen_victoria))

# Definir Cutoff (asumimos 0 para margen de victoria, ajustar si es necesario)
cutoff <- 0

# 3. Guardar como base de datos de R (.rds) en 04_mart
# Construir ruta de salida
output_dir <- dirname(data_path)
saveRDS(df_rdd, file = file.path(output_dir, "final_database_rdd.rds"))
message("Base de datos guardada en: ", file.path(output_dir, "final_database_rdd.rds"))

# 4. Correr Regresión Discontinua (RDD) - Multiples Especificaciones
# Variable dependiente: HHI
# Running variable: margen_victoria

# Definir variables
y_var <- df_rdd$HHI
x_var <- df_rdd$margen_victoria

# Preparar matrices para modelos con controles
vars_controls <- c("log_valor_ctrl", "num_contratos_ctrl", "HHI_ctrl", "pct_simplif_value_ctrl")
df_clean <- df_rdd %>% 
  drop_na(all_of(vars_controls)) %>%
  filter(!is.na(HHI))

y_clean <- df_clean$HHI
x_clean <- df_clean$margen_victoria
covs_clean <- df_clean %>% select(all_of(vars_controls))

# --- Estimaciones ---

# 1. Modelo Base: Lineal, Sin Controles, BW Óptimo
# Nota: Usamos y_clean / x_clean para asegurar que la muestra sea la misma (obs sin NAs en controles)
m1_base <- rdrobust(y = y_clean, x = x_clean, c = cutoff, p = 1)

# 2. Modelo Principal: Lineal, Con Controles, BW Óptimo
m2_main <- rdrobust(y = y_clean, x = x_clean, c = cutoff, covs = covs_clean, p = 1)
bw_opt <- m2_main$bws[1, 1] # Capturar el ancho de banda óptimo (MSE)

# 3. Polinomio Cuadrático (p=2), Con Controles, BW Óptimo
m3_quad <- rdrobust(y = y_clean, x = x_clean, c = cutoff, covs = covs_clean, p = 2)

# 4. Ancho de Banda Mitad (0.5x), Lineal, Con Controles
m4_halfbw <- rdrobust(y = y_clean, x = x_clean, c = cutoff, covs = covs_clean, p = 1, h = 0.5 * bw_opt)

# 5. Ancho de Banda Doble (2.0x), Lineal, Con Controles
m5_doublebw <- rdrobust(y = y_clean, x = x_clean, c = cutoff, covs = covs_clean, p = 1, h = 2.0 * bw_opt)


# Función auxiliar ajustada para incluir metadatos
extract_rd_details <- function(model, name, poly, bw_type) {
  data.frame(
    Especificacion = name,
    Coeficiente = sprintf("%.3f", model$coef["Robust",]),
    SE = sprintf("(%.3f)", model$se["Robust",]),
    P_value = sprintf("%.3f", model$pv["Robust",]),
    Obs = sum(model$N),
    Polinomio = paste0("Grado ", poly),
    Bandwidth = sprintf("%.3f", model$bws["h", "left"]),
    BW_Type = bw_type
  )
}

# Compilar resultados
rows <- list(
  extract_rd_details(m1_base, "Sin Controles", 1, "Óptimo"),
  extract_rd_details(m2_main, "Con Controles", 1, "Óptimo"),
  extract_rd_details(m3_quad, "Cuadrático", 2, "Óptimo"),
  extract_rd_details(m4_halfbw, "BW 0.5x", 1, "0.5 * MSE"),
  extract_rd_details(m5_doublebw, "BW 2.0x", 1, "2.0 * MSE")
)

results_table <- bind_rows(rows)

# Generar tabla LaTeX consolidada y guardar en stores
latex_out <- stargazer(results_table, summary = FALSE, type = "latex", 
                       title = "Resultados RDD: Robustez ante BW y Polinomios (Var: HHI)", 
                       rownames = FALSE)
writeLines(latex_out, con = store_file("rdd_results_hhi.tex"))

# 7. Graficar la regresión discontinua
# Usando rdplot para visualización automática de bines y polinomios
png(filename = store_file("rdd_plot_hhi.png"), width = 800, height = 600)
rdplot(
  y = y_clean,
  x = x_clean,
  c = cutoff,
  title = "Regresión Discontinua: HHI vs Margen de Victoria",
  y.label = "HHI",
  x.label = "Margen de Victoria"
)
dev.off()

# 8. Pruebas de Robustez

# a) Prueba de No Manipulación (McCrary Density Test)
# Se usa la variable de asignación original o limpia según preferencia; usualmente se reporta sobre la muestra usada.
dens_test <- rddensity(x_clean, c = cutoff)
summary(dens_test)

# Guardar gráfico McCrary en stores
png(filename = store_file("rdd_mccrary_density.png"), width = 800, height = 600)
rdplotdensity(dens_test, x_clean, 
              xlabel = "Margen de Victoria", 
              title = "Prueba de Densidad (McCrary)")
dev.off()

# b) Pruebas de continuidad de las variables de control
# Se corre un RDD usando los controles como variable dependiente ("placebo test")
# Usamos df_clean para consistencia

# Control 1: num_contratos_ctrl
rd_check_1 <- rdrobust(y = df_clean$num_contratos_ctrl, x = df_clean$margen_victoria, c = cutoff)
summary(rd_check_1)

png(filename = store_file("rdd_continuity_num_contratos.png"), width = 800, height = 600)
rdplot(y = df_clean$num_contratos_ctrl, x = df_clean$margen_victoria, c = cutoff,
       title = "Continuidad: Numero Contratos", y.label = "Num Contratos")
dev.off()

# Control 2: log_valor_ctrl
rd_check_2 <- rdrobust(y = df_clean$log_valor_ctrl, x = df_clean$margen_victoria, c = cutoff)
summary(rd_check_2)

png(filename = store_file("rdd_continuity_log_valor.png"), width = 800, height = 600)
rdplot(y = df_clean$log_valor_ctrl, x = df_clean$margen_victoria, c = cutoff,
       title = "Continuidad: Log Valor de Contratos", y.label = "Log Valor")
dev.off()

# ==============================================================================
# SEGUNDA VARIABLE DEPENDIENTE: % Valor Contratos Simplificados (pct_simplif_value)
# ==============================================================================

# Preparar matrices para modelos con controles (Sample 2)
# Aseguramos muestra limpia para esta variable
df_clean_val <- df_rdd %>% 
  drop_na(all_of(vars_controls)) %>%
  filter(!is.na(pct_simplif_value))

y_clean_val <- df_clean_val$pct_simplif_value
x_clean_val <- df_clean_val$margen_victoria
covs_clean_val <- df_clean_val %>% select(all_of(vars_controls))

# --- Estimaciones (Valor) ---

# 1. Modelo Base: Lineal, Sin Controles, BW Óptimo
m1_base_val <- rdrobust(y = y_clean_val, x = x_clean_val, c = cutoff, p = 1)

# 2. Modelo Principal: Lineal, Con Controles, BW Óptimo
m2_main_val <- rdrobust(y = y_clean_val, x = x_clean_val, c = cutoff, covs = covs_clean_val, p = 1)
bw_opt_val <- m2_main_val$bws[1, 1] # Capturar el ancho de banda óptimo (MSE)

# 3. Polinomio Cuadrático (p=2), Con Controles, BW Óptimo
m3_quad_val <- rdrobust(y = y_clean_val, x = x_clean_val, c = cutoff, covs = covs_clean_val, p = 2)

# 4. Ancho de Banda Mitad (0.5x), Lineal, Con Controles
m4_halfbw_val <- rdrobust(y = y_clean_val, x = x_clean_val, c = cutoff, covs = covs_clean_val, p = 1, h = 0.5 * bw_opt_val)

# 5. Ancho de Banda Doble (2.0x), Lineal, Con Controles
m5_doublebw_val <- rdrobust(y = y_clean_val, x = x_clean_val, c = cutoff, covs = covs_clean_val, p = 1, h = 2.0 * bw_opt_val)

# Compilar resultados para tabla
rows_val <- list(
  extract_rd_details(m1_base_val, "Sin Controles", 1, "Óptimo"),
  extract_rd_details(m2_main_val, "Con Controles", 1, "Óptimo"),
  extract_rd_details(m3_quad_val, "Cuadrático", 2, "Óptimo"),
  extract_rd_details(m4_halfbw_val, "BW 0.5x", 1, "0.5 * MSE"),
  extract_rd_details(m5_doublebw_val, "BW 2.0x", 1, "2.0 * MSE")
)

results_table_val <- bind_rows(rows_val)

# Generar tabla LaTeX consolidada y guardar en stores
latex_out_val <- stargazer(results_table_val, summary = FALSE, type = "latex", 
                           title = "Resultados RDD: Robustez ante BW y Polinomios (Var: pct_simplif_value)", 
                           rownames = FALSE)
writeLines(latex_out_val, con = store_file("rdd_results_pct_simplif_value.tex"))

# Graficar la regresión discontinua y guardar
png(filename = store_file("rdd_plot_pct_simplif_value.png"), width = 800, height = 600)
rdplot(
  y = y_clean_val,
  x = x_clean_val,
  c = cutoff,
  title = "Regresión Discontinua: % Simplificado (Valor) vs Margen de Victoria",
  y.label = "% Simplificado (Valor)",
  x.label = "Margen de Victoria"
)
dev.off()

