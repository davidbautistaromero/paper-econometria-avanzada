import pandas as pd
import os
import numpy as np

# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------
RAW_DIR = os.path.join("datasets", "01_raw")
SECOP2_FILE = os.path.join(RAW_DIR, "secop2_contratacion.csv")
OUTPUT_FILE = os.path.join("datasets", "02_intermediate", "secop2_intermediate.csv")

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

def clean_and_process_secop2(df):
    print("Limpiando SECOP II...")
    # Filtros específicos SECOP II
    
    # Criterio 1: Columna 'adjudicado' (Si/No) - Es la más confiable si existe
    if "adjudicado" in df.columns:
        # Normalizamos a string por si acaso
        mask_adjudicado = df["adjudicado"].astype(str).str.lower().isin(['si', 'sí', 'true', '1'])
        df = df[mask_adjudicado]
    
    # Criterio 2: Estado del procedimiento (Backup o filtro adicional si se requiere)
    # Si ya filtramos por adjudicado='Si', el estado debería ser congruente, pero a veces hay 'Adjudicado' sin 'Si' explícito?
    # En SECOP II, adjudicado='Si' suele ser el flag final.
    # Si NO existiera columna adjudicado, usaríamos estado.
    elif "estado_del_procedimiento" in df.columns:
        valid_states = ['Adjudicado', 'Celebrado', 'Seleccionado'] # Agregamos Seleccionado si es relevante
        df = df[df["estado_del_procedimiento"].isin(valid_states)]
        
    # Filtro valor > 0
    if "valor_total_adjudicacion" in df.columns:
        df["valor_total_adjudicacion"] = pd.to_numeric(df["valor_total_adjudicacion"], errors='coerce')
        df = df[df["valor_total_adjudicacion"] > 0]
        
    # Filtro fecha adjudicacion
    if "fecha_adjudicacion" in df.columns:
        df = df.dropna(subset=["fecha_adjudicacion"])
        
    df["origen_dato"] = "SECOP II"
    return df

def process_secop2():
    if not os.path.exists(SECOP2_FILE):
        print(f"Advertencia: No se encontró archivo SECOP II en {SECOP2_FILE}")
        return
    
    print(f"Procesando SECOP II ({SECOP2_FILE})...")
    header2 = pd.read_csv(SECOP2_FILE, nrows=0).columns.tolist()
    map_s2 = {c: c.lower().replace(" ", "_") for c in header2}
    
    try:
        df2 = pd.read_csv(SECOP2_FILE)
        df2 = df2.rename(columns=map_s2)
        
        # Normalización de nombres clave antes de limpiar
        if "nit_de_la_entidad" in df2.columns and "nit_entidad" not in df2.columns:
            df2["nit_entidad"] = df2["nit_de_la_entidad"]
        
        # Limpieza
        df2 = clean_and_process_secop2(df2)
        
        # Asegurar columnas
        for col in COLS_KEEP:
            if col not in df2.columns:
                df2[col] = None
                        
        df2 = df2[COLS_KEEP]
        print(f"  -> {len(df2)} registros limpios de SECOP II")
        
        # Guardar
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        print(f"Guardando en {OUTPUT_FILE}...")
        df2.to_csv(OUTPUT_FILE, index=False)
        print("Proceso finalizado.")
        
    except Exception as e:
        print(f"Error leyendo SECOP II: {e}")

if __name__ == "__main__":
    process_secop2()

