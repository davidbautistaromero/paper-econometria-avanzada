import pandas as pd
import unicodedata
import os
import requests
from io import StringIO

# Rutas
OUTPUT_FILE = os.path.join("datasets", "03_primary", "municipios_colombia.csv")
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# URL de Datos Abiertos Colombia (Divipola)
# gdxc-w37w es el ID del dataset de "División Política Administrativa de Colombia"
URL = "https://www.datos.gov.co/resource/gdxc-w37w.csv?$limit=2000"

def normalize_text(text):
    if pd.isna(text):
        return ""
    s = str(text).lower().strip()
    s = unicodedata.normalize('NFD', s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s

print(f"Descargando lista de municipios desde {URL}...")
try:
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    
    # Cargar a Pandas
    df = pd.read_csv(StringIO(response.text))
    
    # Inspeccionar columnas
    # Usualmente vienen como 'dpto_ccdgo', 'dpto_cnmbr', 'mpio_ccdgo', 'mpio_cnmbr', etc.
    # Ajustar nombres si es necesario
    print("Columnas encontradas:", df.columns.tolist())
    
    # Seleccionar nombres de departamento y municipio
    col_dept = 'dpto'
    col_mun = 'nom_mpio'
    
    print(f"Usando columnas: {col_dept} (Depto), {col_mun} (Mpio)")
    
    # Crear dataframe final normalizado
    out = pd.DataFrame()
    out['departamento'] = df[col_dept].apply(normalize_text)
    out['municipio'] = df[col_mun].apply(normalize_text)
    
    # Ordenar y eliminar duplicados
    out = out.drop_duplicates().sort_values(['departamento', 'municipio'])
    
    # Guardar
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"Archivo guardado en: {OUTPUT_FILE}")
    print(f"Total municipios: {len(out)}")
    print(out.head())

except Exception as e:
    print(f"Error descargando/procesando: {e}")

