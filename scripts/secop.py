import pandas as pd
import numpy as np
import unicodedata
import os

# -------------------------------------------------------------------
# CONFIGURACIÓN Y RUTAS
# -------------------------------------------------------------------
SECOP1_FILE = os.path.join("datasets", "02_intermediate", "secop1_intermediate.csv")
SECOP2_FILE = os.path.join("datasets", "02_intermediate", "secop2_intermediate.csv")
OUTPUT_DIR = os.path.join("datasets", "03_primary")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "secop.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------------------------
def normalize_txt(txt):
    if pd.isna(txt): return np.nan
    t = str(txt).strip().lower()
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    # Eliminar ñ explícitamente
    t = t.replace("ñ", "") 
    t = ' '.join(t.split())
    return t

def normalize_ciudad(txt):
    """Normaliza ciudad: minúsculas, sin tildes, elimina ñ"""
    if pd.isna(txt): return np.nan
    t = str(txt).strip().lower()
    # Quitar tildes
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    # Eliminar ñ
    t = t.replace("ñ", "")
    t = t.replace("Ñ", "")
    t = ' '.join(t.split())
    return t

def normalize_departamento(txt):
    """Normaliza departamento: minúsculas, sin tildes, reemplaza ñ por n"""
    if pd.isna(txt): return np.nan
    t = str(txt).strip().lower()
    # Quitar tildes
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    # Reemplazar ñ por n
    t = t.replace("ñ", "n")
    t = t.replace("Ñ", "n")
    t = ' '.join(t.split())
    return t

def is_simplificada(m):
    if pd.isna(m): return False
    m = normalize_txt(m)
    if pd.isna(m): return False
    if m.startswith('enajenacion') or 'subasta de prueba' in m or m.startswith('solicitud de informacion'):
        return False
    if 'contratacion directa' in m: return True
    if 'minima cuantia' in m: return True
    if 'seleccion abreviada' in m and 'menor cuantia' in m and 'subasta inversa' not in m: return True
    if 'regimen especial' in m: return True
    return False

# -------------------------------------------------------------------
# CARGA Y CONCATENACIÓN
# -------------------------------------------------------------------
print("Cargando SECOP1...")
df1 = pd.read_csv(SECOP1_FILE)

print("Cargando SECOP2")
df2 = pd.read_csv(SECOP2_FILE)

print("Concatenando datasets...")
df = pd.concat([df1, df2], ignore_index=True)

# -------------------------------------------------------------------
# PREPARACIÓN Y LIMPIEZA
# -------------------------------------------------------------------
print("Preparando y limpiando datos...")

# Convertir fecha_adjudicacion a datetime
df['fecha_adjudicacion'] = pd.to_datetime(df['fecha_adjudicacion'], errors='coerce')
df['valor_total_adjudicacion'] = pd.to_numeric(df['valor_total_adjudicacion'], errors='coerce')

# 1. Filtro de fechas (2015 hasta 2023)
df = df.dropna(subset=["fecha_adjudicacion"])
df["year"] = df["fecha_adjudicacion"].dt.year
df = df[df["year"].isin([2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023])]

# 2. Filtro básico de adjudicación
is_awarded = (
    df['valor_total_adjudicacion'].gt(0) &
    (
        df['adjudicado'].astype(str).str.strip().str.lower().isin(['si', 'sí', 'true', '1']) 
    )
)
df = df[is_awarded].copy()

# 3. Normalizar NIT Entidad
df["nit_entidad"] = df["nit_entidad"].astype(str).str.replace(r'[^0-9]', '', regex=True)
df["nit_entidad"] = pd.to_numeric(df["nit_entidad"], errors='coerce')
df = df.dropna(subset=["nit_entidad"])
df["nit_entidad"] = df["nit_entidad"].astype(np.int64)

# 4. Columna Alcaldía
df['alcaldia'] = df['entidad'].astype(str).str.lower().str.contains('alcaldia|alcaldía|municipio', regex=True).astype(int)

# 5. NIT Proveedor
df["nit_prov"] = df["nit_del_proveedor_adjudicado"].fillna("")
df["nit_prov"] = df["nit_prov"].astype(str).str.replace(r'[^0-9]', '', regex=True)
df["nit_prov"] = df["nit_prov"].replace("", np.nan)

# 6. Simplificada
df['simplificada'] = df['modalidad_de_contratacion'].apply(is_simplificada)

# -------------------------------------------------------------------
# DATOS PERIODO INTERÉS (2020-2023)
# -------------------------------------------------------------------
print("Procesando periodo de interés (2020-2023)...")
df_main = df[df["year"].between(2020, 2023)].copy()
df_main["periodo"] = "2020-2023"

# Filtro >= 2 contratos en 2020-2023
contract_counts_main = df_main.groupby("nit_entidad")["id_del_proceso"].nunique().reset_index(name="num_contratos")
df_main = df_main.merge(contract_counts_main, on="nit_entidad", how="inner")
df_main = df_main[df_main["num_contratos"] >= 2].copy()

# Agrupar solo por nit_entidad (y otras columnas descriptivas)
group_keys = ["nit_entidad"]

# Obtener información descriptiva de la entidad (priorizar SECOP II sobre SECOP I)
# Ordenar para que SECOP II quede primero (orden descendente alfabético)
df_main_sorted = df_main.sort_values("origen_dato", ascending=False)

entity_info = df_main_sorted.groupby("nit_entidad").agg({
    "entidad": "first",
    "departamento_entidad": "first",
    "ciudad_entidad": "first",
    "alcaldia": "first",
    "num_contratos": "first"
}).reset_index()

# -------------------------------------------------------------------
# RECUPERACIÓN DE CIUDADES "NO DEFINIDO" DESDE NOMBRE DE ENTIDAD
# -------------------------------------------------------------------
print("Recuperando ciudades 'No Definido' desde nombre de entidad...")
MUNICIPIOS_FILE = os.path.join("datasets", "03_primary", "municipios_colombia.csv")

if os.path.exists(MUNICIPIOS_FILE):
    df_mun = pd.read_csv(MUNICIPIOS_FILE)
    # Normalizar municipios y departamentos
    df_mun['municipio_norm'] = df_mun['municipio'].apply(normalize_ciudad)
    df_mun['departamento_norm'] = df_mun['departamento'].apply(normalize_departamento)
    
    # Crear diccionario de municipio -> departamento (solo municipios únicos)
    mun_counts = df_mun['municipio_norm'].value_counts()
    unique_muns = mun_counts[mun_counts == 1].index
    df_mun_unique = df_mun[df_mun['municipio_norm'].isin(unique_muns)].set_index('municipio_norm')
    mun_to_dept = df_mun_unique['departamento_norm'].to_dict()
    
    # Normalizar nombre de entidad para búsqueda
    entity_info['entidad_norm'] = entity_info['entidad'].apply(normalize_txt)
    
    # Identificar filas con ciudad "no definido"
    mask_no_def = (
        (entity_info["ciudad_entidad"].astype(str).str.lower() == "no definido") | 
        (entity_info["ciudad_entidad"].isna()) | 
        (entity_info["ciudad_entidad"].astype(str).str.strip() == "")
    )
    
    print(f"Filas con ciudad 'No Definido' antes: {mask_no_def.sum()}")
    
    # Buscar municipios en el nombre de la entidad
    updates = []
    for idx in entity_info[mask_no_def].index:
        ent_name_norm = entity_info.loc[idx, 'entidad_norm']
        if pd.isna(ent_name_norm):
            continue
            
        # Buscar el municipio más largo que esté contenido en el nombre de la entidad
        found_mun = None
        found_dept = None
        max_len = 0
        
        for mun_norm, dept_norm in mun_to_dept.items():
            if len(mun_norm) > max_len and len(mun_norm) > 3:  # Evitar coincidencias muy cortas
                if mun_norm in ent_name_norm:
                    found_mun = mun_norm
                    found_dept = dept_norm
                    max_len = len(mun_norm)
        
        if found_mun:
            updates.append((idx, found_mun, found_dept))
    
    print(f"Se encontraron {len(updates)} recuperaciones potenciales.")
    
    # Aplicar actualizaciones
    for idx, mun, dept in updates:
        entity_info.at[idx, 'ciudad_entidad'] = mun
        # Si el departamento también es "no definido", reemplazarlo
        dept_actual = str(entity_info.at[idx, 'departamento_entidad']).lower().strip()
        if dept_actual == "no definido" or dept_actual == "nan" or pd.isna(entity_info.at[idx, 'departamento_entidad']):
            entity_info.at[idx, 'departamento_entidad'] = dept
    
    # Eliminar columna temporal
    entity_info = entity_info.drop(columns=['entidad_norm'])
    
    print(f"Ciudades recuperadas: {len(updates)}")
else:
    print("ADVERTENCIA: No se encontró municipios_colombia.csv, saltando recuperación de ciudades.")

# --- CÁLCULO HHI 2020-2023 ---
g_hhi = (df_main.groupby(group_keys + ["nit_prov"], dropna=False)
        ["valor_total_adjudicacion"].sum()
        .reset_index(name="v_i"))

tot_hhi = (g_hhi.groupby(group_keys)["v_i"]
           .sum()
           .reset_index(name="V"))

m_hhi = g_hhi.merge(tot_hhi, on=group_keys, how="left")
m_hhi = m_hhi[m_hhi["V"] > 0]
m_hhi["s_i"] = m_hhi["v_i"] / m_hhi["V"]

res_hhi = (m_hhi.assign(sq=lambda x: x["s_i"]**2)
           .groupby(group_keys)["sq"]
           .sum()
           .reset_index(name="HHI"))
res_hhi["HHI_10000"] = (res_hhi["HHI"] * 10000).round(0)

# --- CÁLCULO CONCENTRACIÓN 2020-2023 ---
# Corregido: calcular procesos_simplif contando IDs únicos, no sumando filas booleanas
res_conc = (
    df_main.groupby(group_keys).apply(
        lambda x: pd.Series({
            'procesos_simplif': x.loc[x['simplificada'], 'id_del_proceso'].nunique(),
            'valor_total_conc': x['valor_total_adjudicacion'].sum(),
            'valor_simplif': x.loc[x['simplificada'], 'valor_total_adjudicacion'].sum()
        })
    ).reset_index()
)

# Obtener número total de contratos por entidad para calcular porcentajes
contract_counts_for_pct = df_main.groupby("nit_entidad")["id_del_proceso"].nunique().reset_index(name="total_procesos")
res_conc = res_conc.merge(contract_counts_for_pct, on="nit_entidad", how="left")
res_conc['pct_simplif_count'] = res_conc['procesos_simplif'] / res_conc['total_procesos']
res_conc['pct_simplif_value'] = res_conc['valor_simplif'] / res_conc['valor_total_conc']
res_conc = res_conc.drop(columns=['total_procesos'])

# Merge resultados principales
final_df = res_hhi.merge(res_conc, on=group_keys, how="outer")
# Agregar num_contratos desde contract_counts_main
final_df = final_df.merge(contract_counts_main, on="nit_entidad", how="left")
# Agregar información descriptiva de la entidad
final_df = final_df.merge(entity_info[["nit_entidad", "entidad", "departamento_entidad", "ciudad_entidad", "alcaldia"]], on="nit_entidad", how="left")
# Agregar periodo
final_df["periodo"] = "2020-2023"

# Normalizar textos de departamento y ciudad
print("Normalizando textos de departamento y ciudad...")
final_df["departamento_entidad"] = final_df["departamento_entidad"].apply(normalize_departamento)
final_df["ciudad_entidad"] = final_df["ciudad_entidad"].apply(normalize_ciudad)

# -------------------------------------------------------------------
# VARIABLES DE CONTROL (2015 - Septiembre 2019)
# -------------------------------------------------------------------
print("Calculando variables de control (2015 - Sept 2019)...")

def calculate_metrics_custom_period(df_subset, suffix):
    # Filtrar periodo personalizado: >= 2015 y < 2019-10-01
    df_p = df_subset[
        (df_subset["fecha_adjudicacion"] >= "2015-01-01") & 
        (df_subset["fecha_adjudicacion"] < "2019-01-01")
    ].copy()
    
    if df_p.empty:
        return pd.DataFrame(columns=["nit_entidad"])
    
    # Corregido para controles también: usar nunique para evitar > 100%
    # Agregación personalizada usando apply para conteos únicos correctos
    def agg_funcs(x):
        return pd.Series({
            'num_contratos_p': x['id_del_proceso'].nunique(),
            'valor_total_p': x['valor_total_adjudicacion'].sum(),
            'simplificada_count': x.loc[x['simplificada'], 'id_del_proceso'].nunique(),
            'simplificada_valor': x.loc[x['simplificada'], 'valor_total_adjudicacion'].sum()
        })

    aggs = df_p.groupby("nit_entidad").apply(agg_funcs).reset_index()
    
    aggs[f"log_valor_{suffix}"] = np.log(aggs["valor_total_p"] + 1)
    aggs[f"num_contratos_{suffix}"] = aggs["num_contratos_p"]
    
    aggs[f"pct_simplif_count_{suffix}"] = aggs["simplificada_count"] / aggs["num_contratos_p"]
    aggs[f"pct_simplif_value_{suffix}"] = aggs["simplificada_valor"] / aggs["valor_total_p"]
    
    g_prov = (df_p.groupby(["nit_entidad", "nit_prov"])["valor_total_adjudicacion"]
              .sum()
              .reset_index(name="v_i"))
    
    g_prov = g_prov.merge(aggs[["nit_entidad", "valor_total_p"]], on="nit_entidad", how="left")
    g_prov["s_i"] = g_prov["v_i"] / g_prov["valor_total_p"]
    
    hhi_p = (g_prov.assign(sq=lambda x: x["s_i"]**2)
             .groupby("nit_entidad")["sq"]
             .sum()
             .reset_index(name=f"HHI_{suffix}"))
             
    hhi_p[f"HHI_10000_{suffix}"] = (hhi_p[f"HHI_{suffix}"] * 10000).round(0)
    
    cols_out = ["nit_entidad", f"num_contratos_{suffix}", f"log_valor_{suffix}", 
                f"HHI_{suffix}", f"HHI_10000_{suffix}", 
                f"pct_simplif_count_{suffix}", f"pct_simplif_value_{suffix}"]
                
    res = aggs.merge(hhi_p, on="nit_entidad", how="left")
    return res[[c for c in cols_out if c in res.columns]]

# Controles unificados: 2015 - Sept 2019
ctrl_combined = calculate_metrics_custom_period(df, "ctrl")

# -------------------------------------------------------------------
# MERGE FINAL CON CONTROLES
# -------------------------------------------------------------------
print("Unificando controles...")

final_df = final_df.merge(ctrl_combined, on="nit_entidad", how="left")

# Reordenar columnas
base_cols = ["nit_entidad", "entidad", "departamento_entidad", "ciudad_entidad", "periodo", "alcaldia", "num_contratos"]
metrics_main = ["HHI", "HHI_10000", "pct_simplif_count", "pct_simplif_value", "procesos_simplif", "valor_simplif", "valor_total_conc"]

ctrl_cols = [c for c in final_df.columns if c not in base_cols + metrics_main]
ctrl_cols.sort() 

final_cols = base_cols + metrics_main + ctrl_cols
final_df = final_df[[c for c in final_cols if c in final_df.columns]]

final_df.to_csv(OUTPUT_FILE, index=False)
print(f"Filas procesadas: {len(final_df)}")
print(f"Archivo guardado en: {OUTPUT_FILE}")
