import pandas as pd
import unicodedata
import re
import os

# Rutas de entrada/salida
INPUT_CSV = os.path.join("datasets", "02_intermediate", "resultados_electorales_intermediate.csv")
OUTPUT_CSV = os.path.join("datasets", "03_primary", "outsiders.csv")

# -------------------------------------------------------------------
# 1. Cargar base de datos
# -------------------------------------------------------------------
df = pd.read_csv(INPUT_CSV)

# -------------------------------------------------------------------
# 2. Normalización de nombres
# -------------------------------------------------------------------
def normalize_name(name: str) -> str:
    if pd.isna(name):
        return ""
    name = str(name).lower()
    name = unicodedata.normalize("NFD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    
    # Correcciones manuales
    if name == "norte de san":
        name = "norte de santander"
        
    return name

# -------------------------------------------------------------------
# 3. Lista de partidos oficiales
# -------------------------------------------------------------------
official_orgs_raw = [
    "AGRUPACION POLITICA EN MARCHA", "INDEPENDIENTES", "MOVIMIENTO SALVACION NACIONAL",
    "MOVIMIENTO ALIANZA DEMOCRATICA AMPLIA", "MOVIMIENTO ALTERNATIVO INDIGENA Y SOCIAL MAIS",
    "MOVIMIENTO AUTORIDADES INDIGENAS DE COLOMBIA AICO", "MOVIMIENTO ESPERANZA PAZ Y LIBERTAD",
    "MOVIMIENTO FUERZA CIUDADANA", "MOVIMIENTO POLITICO COLOMBIA HUMANA", "NUEVA FUERZA DEMOCRATICA",
    "PARTIDO ALIANZA SOCIAL INDEPENDIENTE ASI", "PARTIDO ALIANZA VERDE", "PARTIDO CAMBIO RADICAL",
    "PARTIDO CENTRO DEMOCRATICO", "PARTIDO COLOMBIA JUSTA LIBRES", "PARTIDO COLOMBIA RENACIENTE",
    "PARTIDO COMUNES", "PARTIDO COMUNISTA COLOMBIANO", "PARTIDO CONSERVADOR COLOMBIANO",
    "PARTIDO DE LA UNION POR LA GENTE PARTIDO DE LA U", "PARTIDO SOCIAL DE UNIDAD NACIONAL  PARTIDO DE LA U",
    "PARTIDO DEL TRABAJO DE COLOMBIA PTC", "PARTIDO DEMOCRATA COLOMBIANO", "PARTIDO ECOLOGISTA COLOMBIANO",
    "PARTIDO LIBERAL COLOMBIANO", "LIGA DE GOBERNANTES ANTICORRUPCION", "PARTIDO NUEVO LIBERALISMO",
    "PARTIDO POLO DEMOCRATICO ALTERNATIVO", "PARTIDO POLITICO CREEMOS", "PARTIDO POLITICO DIGNIDAD",
    "PARTIDO POLITICO GENTE EN MOVIMIENTO", "PARTIDO POLITICO LA FUERZA DE LA PAZ", "PARTIDO POLITICO MIRA",
    "PARTIDO UNION PATRIOTICA UP", "PARTIDO VERDE OXIGENO", "TODOS SOMOS COLOMBIA",
]
official_norms = [normalize_name(x) for x in official_orgs_raw]

# -------------------------------------------------------------------
# 4. Clasificar outsiders
# -------------------------------------------------------------------
def is_outsider(party_name: str) -> int:
    n = normalize_name(party_name)
    if not n: return 1
    for off in official_norms:
        if off in n or n in off:
            return 0
    return 1

df["outsider"] = df["Nombre Partido"].apply(is_outsider)

# -------------------------------------------------------------------
# 5. Normalizar nombres de ubicación
# -------------------------------------------------------------------
col_dept = "Nombre Departamento"
col_mun = "Nombre Municipio"
if col_dept in df.columns: df[col_dept] = df[col_dept].astype(str).apply(normalize_name)
if col_mun in df.columns: df[col_mun] = df[col_mun].astype(str).apply(normalize_name)

# -------------------------------------------------------------------
# 6. Filtrar municipios MIXTOS (outsider y no outsider)
# -------------------------------------------------------------------
# IMPORTANTE: Agrupar por Departamento + Municipio (código o nombre)
# porque el Código Municipio (1, 2, 3...) se repite entre departamentos.

# Verificar si existen códigos
has_cod_dept = "Código Departamento" in df.columns
has_cod_mun = "Código Municipio" in df.columns

if has_cod_dept and has_cod_mun:
    group_cols = ["Código Departamento", "Código Municipio"]
    print("Agrupando por [Código Departamento, Código Municipio]")
else:
    group_cols = [col_dept, col_mun]
    print(f"Agrupando por [{col_dept}, {col_mun}]")

# Identificar municipios mixtos
mask_mixed = df.groupby(group_cols)["outsider"].transform(lambda s: s.nunique() == 2)
filtered_df = df[mask_mixed].copy()

print(f"\nFilas originales: {len(df)}")
print(f"Filas filtradas (mixtos): {len(filtered_df)}")

# -------------------------------------------------------------------
# 7. Reestructurar: Una fila por municipio (comparativa)
# -------------------------------------------------------------------
# Para cada municipio, queremos el mejor outsider y el mejor no outsider

# Identificar el ganador de cada bando en cada municipio
# Ordenar por votos descendente
filtered_df = filtered_df.sort_values(group_cols + ["outsider", "Total Votos"], ascending=[True, True, True, False])

# Tomar el top 1 de cada bando por municipio
best_candidates = filtered_df.groupby(group_cols + ["outsider"]).first().reset_index()

# Separar outsiders y no outsiders
outsiders = best_candidates[best_candidates["outsider"] == 1].copy()
non_outsiders = best_candidates[best_candidates["outsider"] == 0].copy()

# Renombrar columnas para el merge
suffix_out = "_outsider"
suffix_non = "_no_outsider"

cols_to_rename = {
    "Nombre Candidato": "candidato",
    "Código Partido": "cod_partido",
    "Nombre Partido": "partido",
    "Total Votos": "votos"
}

# Función para renombrar manteniendo keys de cruce intactas
def prepare_df(d, suffix):
    rename_map = {k: f"{v}{suffix}" for k, v in cols_to_rename.items()}
    # Mantener group_cols y otras identificadoras sin cambio
    return d.rename(columns=rename_map)

outsiders_ready = prepare_df(outsiders, suffix_out)
non_outsiders_ready = prepare_df(non_outsiders, suffix_non)

# Columnas base para el merge (ubicación + año si existe)
merge_cols = group_cols + ["Código Departamento", "Nombre Departamento", "Código Municipio", "Nombre Municipio", "Año"]
# Eliminar duplicados en merge_cols (que ya están en group_cols)
merge_cols = list(set(merge_cols).intersection(outsiders_ready.columns))

final_df = pd.merge(
    outsiders_ready,
    non_outsiders_ready,
    on=merge_cols,
    how="inner"
)

# Calcular diferencias
final_df["diferencia_votos"] = final_df["votos_outsider"] - final_df["votos_no_outsider"]
final_df["total_votos_top2"] = final_df["votos_outsider"] + final_df["votos_no_outsider"]
final_df["margen_victoria"] = final_df["diferencia_votos"] / final_df["total_votos_top2"]

# Seleccionar columnas finales ordenadas
cols_order = merge_cols + [
    "candidato_outsider", "partido_outsider", "votos_outsider",
    "candidato_no_outsider", "partido_no_outsider", "votos_no_outsider",
    "diferencia_votos", "margen_victoria"
]

# Filtrar solo las columnas que existen
final_df = final_df[[c for c in cols_order if c in final_df.columns]]

# -------------------------------------------------------------------
# 8. Guardar
# -------------------------------------------------------------------
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
final_df.to_csv(OUTPUT_CSV, index=False)
print(f"\nArchivo final estructurado generado: {OUTPUT_CSV}")
print(f"Total municipios únicos finales: {len(final_df)}")
print("Estructura: Una fila por municipio con comparativa Outsider vs No Outsider")
