# Script de Estadísticas Descriptivas
# Genera tablas resumen de las variables principales para el paper

# 1. Configuración inicial
if (file.exists("scripts/00_config.R")) {
  source("scripts/00_config.R")
} else {
  source("00_config.R")
}

# 2. Cargar datos
data_path <- "datasets/04_mart/final_database.csv"
if (!file.exists(data_path)) {
  data_path <- "../datasets/04_mart/final_database.csv"
}

df <- read_csv(data_path)

# Filtrar base usada en regresiones (con HHI, margen y controles definidos)
df_analysis <- df %>%
  filter(!is.na(HHI), !is.na(margen_victoria)) %>%
  filter(!is.na(HHI_ctrl), !is.na(log_valor_ctrl), !is.na(num_contratos_ctrl))

# 3. Selección de variables para estadística descriptiva
# Variables de resultado (Outcome), Running Variable y Controles
vars_desc <- c(
  "HHI",                   # Outcome principal 1
  "pct_simplif_value",     # Outcome principal 2
  "margen_victoria",       # Running variable
  "num_contratos",         # Contexto
  "valor_total_conc",      # Contexto (Valor total contratado)
  "HHI_ctrl",              # Control (histórico)
  "log_valor_ctrl",        # Control
  "num_contratos_ctrl"     # Control
)

# Nombres legibles para la tabla
var_labels <- c(
  "HHI (Concentración)",
  "% Valor Simplificado",
  "Margen de Victoria",
  "Número de Contratos (2020-2023)",
  "Valor Total Contratado (2020-2023)",
  "HHI Histórico (2015-2019)",
  "Log Valor Histórico",
  "Num. Contratos Histórico"
)

# 4. Generación de Tabla de Estadísticas Descriptivas (General)
stargazer(
  df_analysis %>% select(all_of(vars_desc)) %>% as.data.frame(),
  type = "latex",
  title = "Estadísticas Descriptivas Generales",
  summary.stat = c("n", "mean", "sd", "min", "max", "median"),
  covariate.labels = var_labels,
  digits = 2,
  out = store_file("descriptives_general.tex")
)

# 5. Estadísticas Descriptivas por Grupo (Ganó Outsider vs Ganó Tradicional)
# Outsider gana si margen_victoria > 0 (asumiendo cutoff=0)
df_analysis <- df_analysis %>%
  mutate(grupo = ifelse(margen_victoria > 0, "Gana Outsider", "Gana Tradicional"))

# Tabla comparativa de medias
# Usamos dplyr para calcular medias y SD por grupo
tabla_comparativa <- df_analysis %>%
  group_by(grupo) %>%
  summarise(
    across(all_of(vars_desc), list(media = mean, sd = sd), .names = "{.col}_{.fn}"),
    N = n()
  ) %>%
  pivot_longer(cols = -c(grupo, N), names_to = "variable_stat", values_to = "valor") %>%
  separate(variable_stat, into = c("variable", "stat"), sep = "_", extra = "merge") %>%
  pivot_wider(names_from = c(grupo, stat), values_from = valor) 

# Limpiar nombres de variables
tabla_comparativa <- tabla_comparativa %>%
  mutate(variable_clean = case_when(
    variable == "HHI" ~ "HHI (Concentración)",
    variable == "pct_simplif_value" ~ "% Valor Simplificado",
    variable == "margen_victoria" ~ "Margen de Victoria",
    variable == "num_contratos" ~ "Número de Contratos",
    variable == "valor_total_conc" ~ "Valor Total Contratado",
    variable == "HHI_ctrl" ~ "HHI Histórico",
    variable == "log_valor_ctrl" ~ "Log Valor Histórico",
    variable == "num_contratos_ctrl" ~ "Num. Contratos Histórico",
    TRUE ~ variable
  )) %>%
  select(variable_clean, `Gana Tradicional_media`, `Gana Tradicional_sd`, `Gana Outsider_media`, `Gana Outsider_sd`)

# Generar LaTeX manual para la tabla comparativa (stargazer no hace 'by group' fácilmente en una sola tabla ancha)
# Usaremos kableExtra o escritura directa si kableExtra no está disponible, pero para mantenerlo simple y sin dependencias extra:
# Escribiremos un archivo .tex básico.

tex_content <- c(
  "\\begin{table}[!htbp] \\centering",
  "\\caption{Estadísticas Descriptivas por Tipo de Ganador}",
  "\\label{tab:desc_by_group}",
  "\\begin{tabular}{@{\\extracolsep{5pt}}lcccc}",
  "\\\\[-1.8ex]\\hline \\hline \\\\[-1.8ex]",
  "& \\multicolumn{2}{c}{Gana Tradicional} & \\multicolumn{2}{c}{Gana Outsider} \\\\",
  "& Media & SD & Media & SD \\\\",
  "\\hline \\\\[-1.8ex]"
)

for(i in 1:nrow(tabla_comparativa)) {
  row_str <- sprintf(
    "%s & %.2f & %.2f & %.2f & %.2f \\\\",
    tabla_comparativa$variable_clean[i],
    tabla_comparativa$`Gana Tradicional_media`[i],
    tabla_comparativa$`Gana Tradicional_sd`[i],
    tabla_comparativa$`Gana Outsider_media`[i],
    tabla_comparativa$`Gana Outsider_sd`[i]
  )
  tex_content <- c(tex_content, row_str)
}

tex_content <- c(
  tex_content,
  "\\hline \\\\[-1.8ex]",
  "\\end{tabular}",
  "\\end{table}"
)

writeLines(tex_content, con = store_file("descriptives_by_group.tex"))

# 6. Histogramas de HHI y % Valor Simplificado
# -------------------------------------------------

# Definir tema personalizado para gráficos tipo paper
theme_paper <- theme_bw() +
  theme(
    text = element_text(family = "serif", color = "black"),
    plot.title = element_text(face = "bold", size = 14, hjust = 0.5),
    axis.title = element_text(face = "bold", size = 12),
    axis.text = element_text(size = 10, color = "black"),
    panel.grid.major = element_line(color = "grey90"),
    panel.grid.minor = element_blank(),
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.8)
  )

# a) Histograma de HHI
plot_hhi <- ggplot(df_analysis, aes(x = HHI)) +
  geom_histogram(aes(y = after_stat(density)), bins = 30, fill = "gray80", color = "black", alpha = 0.8) +
  geom_density(color = "darkblue", linewidth = 1) +
  labs(
    title = "Distribución del HHI de Contratación",
    subtitle = "Periodo 2020-2023",
    x = "Índice Herfindahl-Hirschman (HHI)",
    y = "Densidad"
  ) +
  theme_paper

ggsave(filename = store_file("hist_hhi.png"), plot = plot_hhi, width = 8, height = 6, dpi = 300)

# b) Histograma de % Valor Simplificado
plot_simplif <- ggplot(df_analysis, aes(x = pct_simplif_value)) +
  geom_histogram(aes(y = after_stat(density)), bins = 30, fill = "gray80", color = "black", alpha = 0.8) +
  geom_density(color = "darkred", linewidth = 1) +
  labs(
    title = "Distribución del % Valor en Contratación Simplificada",
    subtitle = "Periodo 2020-2023",
    x = "Proporción del Valor Total Contratado (0-1)",
    y = "Densidad"
  ) +
  theme_paper

ggsave(filename = store_file("hist_pct_simplif_value.png"), plot = plot_simplif, width = 8, height = 6, dpi = 300)

