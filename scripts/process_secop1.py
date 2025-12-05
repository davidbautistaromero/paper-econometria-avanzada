import pandas as pd
import os
import numpy as np

# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------
RAW_DIR = os.path.join("datasets", "01_raw")
SECOP1_FILE = os.path.join(RAW_DIR, "secop1_contratacion.csv")
OUTPUT_FILE = os.path.join("datasets", "02_intermediate", "secop1_intermediate.csv")

# Mapeo de columnas SECOP1 a nombres de SECOP2
COL_MAP_SECOP1_TO_SECOP2 = {
    "uid": "id_del_proceso",
    "nombre_entidad": "entidad",
    "nit_de_la_entidad": "nit_entidad",
    "departamento_entidad": "departamento_entidad",
    "municipio_entidad": "ciudad_entidad",
    "modalidad_de_contratacion": "modalidad_de_contratacion",
    "estado_del_proceso": "estado_del_procedimiento",
    "tipo_de_contrato": "tipo_de_contrato",
    "fecha_de_firma_del_contrato": "fecha_adjudicacion",
    "cuantia_contrato": "valor_total_adjudicacion",
    "identificacion_del_contratista": "nit_del_proveedor_adjudicado",
    "nom_razon_social_contratista": "nombre_del_proveedor"
}

# Columnas finales (nombres de SECOP2)
COLS_KEEP = [
    "id_del_proceso",
    "entidad",
    "nit_entidad",
    "departamento_entidad",
    "ciudad_entidad",
    "modalidad_de_contratacion",
    "estado_del_procedimiento",
    "tipo_de_contrato",
    "fecha_adjudicacion",
    "valor_total_adjudicacion",
    "nit_del_proveedor_adjudicado",
    "nombre_del_proveedor",
    "adjudicado",
    "origen_dato"
]

def clean_and_process_secop1(df):
    print("Limpiando SECOP I...")
    # Filtros específicos SECOP I usando nombres originales de columnas
    
    # Filtro por estado del proceso (nombre original: estado_del_proceso)
    valid_states = ['Celebrado', 'Liquidado', 'Terminado', 'Adjudicado', 'Ejecución', 'Tramitado']
    estado_col = None
    for col in df.columns:
        if col.lower() == "estado_del_proceso":
            estado_col = col
            break
    
    if estado_col:
        df[estado_col] = df[estado_col].astype(str).str.title()
        df = df[df[estado_col].isin(valid_states)]
    
    # Filtro por cuantía del contrato (nombre original: cuantia_contrato)
    cuantia_col = None
    for col in df.columns:
        if col.lower() == "cuantia_contrato":
            cuantia_col = col
            break
    
    if cuantia_col:
        df[cuantia_col] = pd.to_numeric(df[cuantia_col], errors='coerce')
        df = df[df[cuantia_col] > 0]
    
    # Filtro por fecha de firma del contrato (nombre original: fecha_de_firma_del_contrato)
    fecha_col = None
    for col in df.columns:
        if col.lower() == "fecha_de_firma_del_contrato":
            fecha_col = col
            break
    
    if fecha_col:
        df = df.dropna(subset=[fecha_col])
    
    # Agregar columnas adicionales
    df["adjudicado"] = "Si"
    df["origen_dato"] = "SECOP I"
    
    return df

def process_secop1():
    if not os.path.exists(SECOP1_FILE):
        print(f"Advertencia: No se encontró archivo SECOP I en {SECOP1_FILE}")
        return
    
    print(f"Procesando SECOP I ({SECOP1_FILE})...")
    
    try:
        # Leer solo las primeras 1000 filas para pruebas
        df1 = pd.read_csv(SECOP1_FILE)
        
        # Limpieza manteniendo nombres originales
        df1 = clean_and_process_secop1(df1)
        
        # Renombrar columnas para que coincidan con SECOP2
        print("  -> Renombrando columnas para coincidir con SECOP2...")
        rename_dict = {}
        for col_original, col_nuevo in COL_MAP_SECOP1_TO_SECOP2.items():
            # Buscar la columna original (puede tener variaciones en mayúsculas/minúsculas)
            for col in df1.columns:
                if col.lower() == col_original.lower():
                    rename_dict[col] = col_nuevo
                    break
        
        df1 = df1.rename(columns=rename_dict)
        
        # Filtrar solo las columnas necesarias para el análisis
        # Asegurar que todas las columnas necesarias existan
        for col in COLS_KEEP:
            if col not in df1.columns:
                df1[col] = None
        
        df1 = df1[COLS_KEEP]
        
        print(f"  -> {len(df1)} registros limpios de SECOP I")
        print(f"  -> Columnas seleccionadas: {len(COLS_KEEP)}")
        
        # Guardar con nombres de columnas estandarizados (iguales a SECOP2)
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        print(f"Guardando en {OUTPUT_FILE}...")
        df1.to_csv(OUTPUT_FILE, index=False)
        print("Proceso finalizado.")
        
    except Exception as e:
        print(f"Error leyendo SECOP I: {e}")

if __name__ == "__main__":
    process_secop1()

