import pandas as pd
import unicodedata
import os
import sys

# -------------------------------------------------------------------
# CONFIGURACIÓN Y RUTAS
# -------------------------------------------------------------------
# Inputs
OUTSIDERS_PATH = os.path.join("datasets", "03_primary", "outsiders.csv")
SECOP_PATH = os.path.join("datasets", "03_primary", "secop.csv")

# Output
OUTPUT_DIR = os.path.join("datasets", "04_mart")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "final_database.csv")
UNMATCHED_FILE = os.path.join(OUTPUT_DIR, "unmatched_cities.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------------------------------------------------
# FUNCIONES DE NORMALIZACIÓN
# -------------------------------------------------------------------
def normalize_text(text):
    """
    Normaliza texto: minúsculas, sin tildes, sin espacios extra, sin caracteres especiales (salvo espacios).
    """
    if pd.isna(text):
        return ""
    s = str(text).lower().strip()
    # Eliminar tildes
    s = unicodedata.normalize('NFD', s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Compactar espacios
    s = " ".join(s.split())
    
    # Correcciones manuales comunes para coincidencia
    s = s.replace("d.c.", "").replace("dc", "").strip()
    s = s.replace("distrito turistico y cultural", "").strip()
    s = s.replace("distrito turistico", "").strip()
    s = s.replace("municipio de ", "").strip()
    
    # Mapeos específicos conocidos (SECOP -> OUTSIDERS)
    replacements = {
        "bogota": "bogota",
        "cartagena de indias": "cartagena",
        "barranquilla": "barranquilla",
        "santa marta": "santa marta",
        "san jose de cucuta": "cucuta",
        "san andres": "san andres",
        "providencia": "providencia"
    }
    return replacements.get(s, s)

# -------------------------------------------------------------------
# CARGA DE DATOS
# -------------------------------------------------------------------
print("Cargando datasets...")

if not os.path.exists(OUTSIDERS_PATH):
    print(f"ERROR: No se encuentra {OUTSIDERS_PATH}")
    sys.exit(1)

if not os.path.exists(SECOP_PATH):
    print(f"ERROR: No se encuentra {SECOP_PATH}")
    sys.exit(1)

df_secop = pd.read_csv(SECOP_PATH)
df_outsiders = pd.read_csv(OUTSIDERS_PATH)

print(f"Filas SECOP: {len(df_secop)}")
print(f"Filas OUTSIDERS (Municipios únicos): {len(df_outsiders)}")

# -------------------------------------------------------------------
# PREPARACIÓN PARA MERGE
# -------------------------------------------------------------------
print("Preparando merge...")

# Identificar columnas de ubicación en Outsiders
col_dept_out = "Nombre Departamento"
col_mun_out = "Nombre Municipio"

if col_dept_out not in df_outsiders.columns:
    # Fallback si los nombres cambiaron
    col_dept_out = [c for c in df_outsiders.columns if "departamento" in c.lower()][0]
    col_mun_out = [c for c in df_outsiders.columns if "municipio" in c.lower()][0]

# Normalizar llaves
print("Normalizando llaves...")

# SECOP
df_secop["dept_norm"] = df_secop["departamento_entidad"].apply(normalize_text)
df_secop["mun_norm"] = df_secop["ciudad_entidad"].apply(normalize_text)

# OUTSIDERS
df_outsiders["dept_norm"] = df_outsiders[col_dept_out].apply(normalize_text)
df_outsiders["mun_norm"] = df_outsiders[col_mun_out].apply(normalize_text)

# -------------------------------------------------------------------
# MERGE (Inner Join a SECOP - Solo Coincidencias)
# -------------------------------------------------------------------
print("Realizando cruce (Inner Join)...")

# Columnas a traer de Outsiders (excluyendo las de ubicación que ya tenemos normalizadas o son redundantes)
cols_to_keep = [c for c in df_outsiders.columns if c not in [col_dept_out, col_mun_out, "Código Departamento", "Código Municipio", "dept_norm", "mun_norm"]]
cols_to_keep += ["dept_norm", "mun_norm"] # Necesarias para el merge

merged = df_secop.merge(
    df_outsiders[cols_to_keep], 
    on=["dept_norm", "mun_norm"], 
    how="inner"
)

# -------------------------------------------------------------------
# DIAGNÓSTICO DE NO MATCHES
# -------------------------------------------------------------------
# Usamos una columna que deba existir si hubo match (ej: candidato_outsider)
check_col = "candidato_outsider"
if check_col not in merged.columns:
    # Si no existe (por alguna razón), tomamos la primera de outsiders
    check_col = cols_to_keep[0]

unmatched = merged[merged[check_col].isna()].copy()

# Filtramos casos donde SECOP tiene "No Definido" porque esos nunca cruzarán
unmatched_clean = unmatched[
    (unmatched["dept_norm"] != "no definido") & 
    (unmatched["mun_norm"] != "no definido") &
    (unmatched["dept_norm"] != "") & 
    (unmatched["mun_norm"] != "")
].copy()

unmatched_cities = unmatched_clean[["departamento_entidad", "ciudad_entidad", "dept_norm", "mun_norm"]].drop_duplicates()

print(f"--------------------------------------------------")
print(f"RESULTADOS DEL CRUCE")
print(f"--------------------------------------------------")
print(f"Total filas SECOP: {len(df_secop)}")
print(f"Filas con match de municipio: {len(merged) - len(unmatched)}")
print(f"Filas sin match: {len(unmatched)} ({len(unmatched)/len(merged):.1%})")
print(f"  -> De las cuales 'No Definido' en SECOP: {len(unmatched) - len(unmatched_clean)}")
print(f"  -> De las cuales con nombre válido pero sin match: {len(unmatched_clean)}")
print(f"Ciudades válidas no encontradas en base Outsiders: {len(unmatched_cities)}")
print(f"--------------------------------------------------")

if len(unmatched_cities) > 0:
    print("Guardando reporte de ciudades no encontradas...")
    unmatched_cities.to_csv(UNMATCHED_FILE, index=False)
    print(f"Reporte guardado en: {UNMATCHED_FILE}")

# -------------------------------------------------------------------
# GUARDADO
# -------------------------------------------------------------------
# Eliminar llaves auxiliares
merged.drop(columns=["dept_norm", "mun_norm"], inplace=True)

print(f"Guardando base final en: {OUTPUT_FILE}")
merged.to_csv(OUTPUT_FILE, index=False)
print("Proceso finalizado.")
