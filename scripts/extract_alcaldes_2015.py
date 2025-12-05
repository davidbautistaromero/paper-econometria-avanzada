#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Extrae los alcaldes electos por municipio (Colombia, 2015) desde una página de Wikipedia
y guarda un CSV en datasets/01_raw/alcaldes_2015.csv.

Uso:
  python extract_alcaldes_2015.py --url "https://<tu_url_de_wikipedia>"
  # o con variable de entorno:
  ALCALDES_2015_URL="https://<tu_url_de_wikipedia>" python extract_alcaldes_2015.py

Parámetros opcionales:
  --out    Ruta de salida (por defecto: datasets/01_raw/alcaldes_2015.csv)

Requisitos:
  - Python 3.8+
  - pandas, requests
  - lxml o bs4 (al menos uno para pd.read_html)
"""

import os
import re
import sys
import argparse
import unicodedata
from io import StringIO
from typing import List, Optional, Tuple

import requests
import pandas as pd
from bs4 import BeautifulSoup


def _norm_text(s: str) -> str:
    s = re.sub(r'\s+', ' ', str(s or '')).strip()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    return s.lower()


def _clean_value(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x)
    # Elimina citas tipo [1], [2], etc.
    s = re.sub(r'\[\d+\]', '', s)
    # Elimina superíndices y símbolos comunes de notas
    s = s.replace('†', '').replace('*', '')
    # Colapsa espacios
    s = re.sub(r'\s+', ' ', s).strip()
    # Reemplaza strings vacíos o "nan"
    if s in ('', 'nan', 'None'):
        return None
    return s


def _extract_tables_by_department(html: str) -> List[Tuple[str, pd.DataFrame]]:
    """
    Extrae tablas asociadas a departamentos.
    Busca divs con clase 'mw-heading mw-heading4' que contienen encabezados h4
    con el nombre del departamento, y extrae la siguiente tabla.
    
    Returns:
        Lista de tuplas (nombre_departamento, dataframe)
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    # Buscar todos los divs con clase mw-heading mw-heading4
    headings = soup.find_all('div', class_='mw-heading mw-heading4')
    
    for heading_div in headings:
        # Extraer el nombre del departamento del h4
        h4 = heading_div.find('h4')
        if not h4:
            continue
            
        # Obtener el texto del departamento (primer enlace o texto directo)
        dept_link = h4.find('a')
        if dept_link:
            departamento = dept_link.get_text(strip=True)
        else:
            departamento = h4.get_text(strip=True)
        
        # Buscar la siguiente tabla después de este encabezado
        current = heading_div
        table = None
        
        # Navegamos hacia adelante buscando la siguiente tabla
        for sibling in heading_div.find_all_next():
            if sibling.name == 'table' and 'wikitable' in sibling.get('class', []):
                table = sibling
                break
            # Si encontramos otro h4, paramos (ya pasamos a otra sección)
            if sibling.name in ['h2', 'h3', 'h4']:
                # Verificamos que no sea el mismo h4 del que venimos
                if sibling != h4:
                    break
        
        if table:
            # Convertir la tabla HTML a string para procesarla con pandas
            table_html = str(table)
            try:
                dfs = pd.read_html(StringIO(table_html), thousands='.')
                if dfs:
                    results.append((departamento, dfs[0]))
            except Exception as e:
                # Silenciosamente ignorar tablas que no se puedan parsear
                pass
    
    return results


def extraer_alcaldes_2015(url: str) -> pd.DataFrame:
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; alcaldes-2015/1.0)'}
    # 1) Intento directo
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        html_main = r.text
    except Exception as e:
        raise RuntimeError(f"No se pudo descargar la página base: {e}")

    # Extraer tablas por departamento
    dept_tables = _extract_tables_by_department(html_main)

    # Si no hubo tablas útiles, probamos con ?action=render
    if not dept_tables or len(dept_tables) == 0:
        sep = '&' if '?' in url else '?'
        render_url = f"{url}{sep}action=render"
        try:
            r2 = requests.get(render_url, headers=headers, timeout=30)
            r2.raise_for_status()
            dept_tables = _extract_tables_by_department(r2.text)
        except Exception:
            pass

    selected = []
    for departamento, df in dept_tables:
        # Aplana MultiIndex si existe
        if isinstance(df.columns, pd.MultiIndex):
            flat_cols = [' '.join([str(x) for x in col if str(x) != 'nan']).strip() for col in df.columns]
            df.columns = flat_cols

        original_cols = [str(c) for c in df.columns]
        # Construimos un mapa normalizado -> original
        norm_map = {_norm_text(c): c for c in original_cols}
        norm_cols = list(norm_map.keys())

        # Heurística de existencia de columnas clave
        has_municipio = any(c in norm_cols for c in [
            'municipio', 'municipio/cabecera', 'municipio o distrito',
            'municipio/ciudad', 'ciudad', 'cabecera', 'municipio-distrito'
        ])
        has_alcalde = any(c.startswith('alcalde') or 'electo' in c or 'candidato electo' in c 
                          or c == 'candidato' or 'candidato ganador' in c
                          for c in norm_cols)
        has_partido = any('partido' in c or 'coalic' in c or 'movimiento' in c for c in norm_cols)

        if not (has_municipio and has_alcalde and has_partido):
            continue

        def pick(col_opts):
            # match exact normalizado
            for opt in col_opts:
                if opt in norm_cols:
                    return opt
            # match por contiene
            for c in norm_cols:
                if any(opt in c for opt in col_opts):
                    return c
            return None

        c_dep = pick(['departamento'])
        c_mun = pick(['municipio', 'municipio/cabecera', 'municipio o distrito',
                      'municipio/ciudad', 'ciudad', 'cabecera'])
        c_alc = pick(['alcalde electo', 'alcalde', 'candidato electo', 'candidato ganador', 
                      'candidato', 'electo'])
        c_par = pick(['partido ganador', 'partido', 'partido/coalicion', 'coalicion', 
                      'partido o coalicion', 'movimiento'])
        c_votos = pick(['votos', 'votacion', 'total votos'])
        c_pct = pick(['%', 'porcentaje', 'pct'])

        if not (c_mun and c_alc and c_par):
            continue

        # Reconstruye a nombres originales "bonitos"
        def original(c):
            return norm_map.get(c, c)

        keep_cols = [c for c in [c_dep, c_mun, c_alc, c_par, c_votos, c_pct] if c]
        # Remapea columnas del df a sus equivalentes normalizadas para seleccionar
        df_tmp = df.copy()
        # Cambiamos a normalizados para seleccionar de forma segura
        df_tmp.columns = norm_cols
        df_out = df_tmp[keep_cols].copy()

        # Renombra a originales y luego a canónicos
        df_out.columns = [original(c) for c in df_out.columns]
        rename_map = {}
        if c_dep:
            rename_map[original(c_dep)] = 'Departamento'
        rename_map[original(c_mun)] = 'Municipio'
        rename_map[original(c_alc)] = 'Alcalde electo'
        rename_map[original(c_par)] = 'Partido'
        if c_votos:
            rename_map[original(c_votos)] = 'Votos'
        if c_pct:
            rename_map[original(c_pct)] = 'Porcentaje'
        df_out = df_out.rename(columns=rename_map)

        # Asegura columna Departamento usando el valor extraído del encabezado
        if 'Departamento' not in df_out.columns:
            df_out.insert(0, 'Departamento', departamento)
        else:
            # Si ya existe pero está vacía, la llenamos con el departamento extraído
            df_out['Departamento'] = df_out['Departamento'].fillna(departamento)

        # Limpieza básica de valores de texto
        for col in ['Departamento', 'Municipio', 'Alcalde electo', 'Partido']:
            if col in df_out.columns:
                df_out[col] = df_out[col].apply(_clean_value)

        # Limpieza de Votos (remover separadores de miles y convertir a entero)
        if 'Votos' in df_out.columns:
            def clean_votos(x):
                val = _clean_value(x)
                if not val or val == 'None':
                    return None
                # Remover puntos (separador de miles) y comas
                val = str(val).replace('.', '').replace(',', '').strip()
                try:
                    return int(val) if val else None
                except:
                    return None
            df_out['Votos'] = df_out['Votos'].apply(clean_votos)
        
        # Limpieza de Porcentaje (remover % y normalizar decimal)
        if 'Porcentaje' in df_out.columns:
            def clean_pct(x):
                val = _clean_value(x)
                if not val or val == 'None':
                    return None
                # Remover % y espacios
                val = str(val).replace('%', '').strip()
                # Reemplazar coma por punto para decimales
                val = val.replace(',', '.')
                try:
                    return float(val) if val else None
                except:
                    return None
            df_out['Porcentaje'] = df_out['Porcentaje'].apply(clean_pct)

        # Remueve filas sin Municipio
        df_out = df_out.dropna(subset=['Municipio'])

        # Ordena columnas
        base_cols = ['Departamento', 'Municipio', 'Alcalde electo', 'Partido']
        optional_cols = ['Votos', 'Porcentaje']
        final_cols = base_cols + [c for c in optional_cols if c in df_out.columns]
        df_out = df_out[final_cols]

        # Filtra filas que son encabezados repetidos o totales
        mask_bad = df_out['Municipio'].str.lower().isin({'municipio', 'total', 'totales'})
        df_out = df_out[~mask_bad]

        if len(df_out):
            selected.append(df_out)

    if not selected:
        # Diagnóstico: departamentos encontrados
        dept_names = [dept for dept, _ in dept_tables]
        raise RuntimeError(
            f"No se encontraron tablas válidas con columnas Municipio/Alcalde/Partido. "
            f"Departamentos encontrados: {dept_names[:20] if dept_names else 'ninguno'}"
        )

    out = pd.concat(selected, ignore_index=True)

    # Deduplicados y trimming final
    for col in ['Departamento', 'Municipio', 'Alcalde electo', 'Partido']:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip().replace({'nan': None, 'None': None, '': None})
    
    # Limpieza de columnas numéricas
    if 'Votos' in out.columns:
        out['Votos'] = out['Votos'].astype(str).str.strip().replace({'nan': None, 'None': None, '': None})
    if 'Porcentaje' in out.columns:
        out['Porcentaje'] = out['Porcentaje'].astype(str).str.strip().replace({'nan': None, 'None': None, '': None})

    out = out.drop_duplicates().reset_index(drop=True)
    return out


def main():
    parser = argparse.ArgumentParser(description="Extrae alcaldes electos 2015 por municipio (Colombia) desde Wikipedia.")
    parser.add_argument('--url', type=str, default=os.environ.get('ALCALDES_2015_URL'),
                        help='URL de Wikipedia con los resultados por municipio (recomendado usar ?action=render).')
    parser.add_argument('--out', type=str, default=os.path.join('datasets', '01_raw', 'alcaldes_2015.csv'),
                        help='Ruta de salida del CSV.')
    args = parser.parse_args()

    if not args.url:
        print("ERROR: Debes proporcionar la URL con --url o la variable de entorno ALCALDES_2015_URL.")
        sys.exit(1)

    # Extrae
    df = extraer_alcaldes_2015(args.url)

    # Crea carpeta de salida
    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Guarda CSV
    df.to_csv(args.out, index=False, encoding='utf-8')
    print(f"Listo. Filas: {len(df)}")
    print(f"CSV guardado en: {args.out}")


if __name__ == '__main__':
    main()