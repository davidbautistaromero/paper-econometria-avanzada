#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Extrae los alcaldes electos por municipio (Colombia, 2015) desde una página de Wikipedia
y guarda un CSV en datasets/02_intermediate/alcaldes_2015.csv.

Uso:
  python extract_alcaldes_2015.py --url "https://<tu_url_de_wikipedia>"
  # o con variable de entorno:
  ALCALDES_2015_URL="https://<tu_url_de_wikipedia>" python extract_alcaldes_2015.py

Parámetros opcionales:
  --out    Ruta de salida (por defecto: datasets/02_intermediate/alcaldes_2015.csv)

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
from typing import List, Optional

import requests
import pandas as pd


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


def _read_all_tables(html: str) -> List[pd.DataFrame]:
    # Intentamos con lxml y luego con bs4 para mayor robustez
    tables = []
    for flavor in (None, 'lxml', 'bs4'):
        try:
            if flavor:
                t = pd.read_html(html, flavor=flavor)
            else:
                t = pd.read_html(html)
            if t:
                tables.extend(t)
        except Exception:
            continue
    # Devolvemos únicas por id de objeto
    seen = set()
    uniq = []
    for df in tables:
        if id(df) not in seen:
            uniq.append(df)
            seen.add(id(df))
    return uniq


def extraer_alcaldes_2015(url: str) -> pd.DataFrame:
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; alcaldes-2015/1.0)'}
    # 1) Intento directo
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        html_main = r.text
    except Exception as e:
        raise RuntimeError(f"No se pudo descargar la página base: {e}")

    tables = _read_all_tables(html_main)

    # Si no hubo tablas útiles, probamos con ?action=render
    if not tables or len(tables) == 0:
        sep = '&' if '?' in url else '?'
        render_url = f"{url}{sep}action=render"
        try:
            r2 = requests.get(render_url, headers=headers, timeout=30)
            r2.raise_for_status()
            tables = _read_all_tables(r2.text)
        except Exception:
            pass

    selected = []
    for df in tables:
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
        c_alc = pick(['alcalde electo', 'alcalde', 'candidato electo', 'electo'])
        c_par = pick(['partido', 'partido/coalicion', 'coalicion', 'partido o coalicion', 'movimiento'])

        if not (c_mun and c_alc and c_par):
            continue

        # Reconstruye a nombres originales "bonitos"
        def original(c):
            return norm_map.get(c, c)

        keep_cols = [c for c in [c_dep, c_mun, c_alc, c_par] if c]
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
        df_out = df_out.rename(columns=rename_map)

        # Asegura columna Departamento (si no venía en la tabla)
        if 'Departamento' not in df_out.columns:
            df_out.insert(0, 'Departamento', pd.NA)

        # Limpieza básica de valores
        for col in ['Departamento', 'Municipio', 'Alcalde electo', 'Partido']:
            df_out[col] = df_out[col].apply(_clean_value)

        # Remueve filas sin Municipio
        df_out = df_out.dropna(subset=['Municipio'])

        # Ordena columnas
        df_out = df_out[['Departamento', 'Municipio', 'Alcalde electo', 'Partido']]

        # Filtra filas que son encabezados repetidos o totales
        mask_bad = df_out['Municipio'].str.lower().isin({'municipio', 'total', 'totales'})
        df_out = df_out[~mask_bad]

        if len(df_out):
            selected.append(df_out)

    if not selected:
        # Diagnóstico: primeros encabezados si bs4 está disponible
        heads_preview = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_main, 'html.parser')
            heads_preview = [h.get_text(' ').strip() for h in soup.select('h2, h3, h4')][:20]
        except Exception:
            pass
        raise RuntimeError(
            "No se encontraron tablas con columnas Municipio/Alcalde/Partido. "
            f"Encabezados detectados (muestra): {heads_preview}"
        )

    out = pd.concat(selected, ignore_index=True)

    # Deduplicados y trimming final
    for col in ['Departamento', 'Municipio', 'Alcalde electo', 'Partido']:
        out[col] = out[col].astype(str).str.strip().replace({'nan': None, 'None': None, '': None})

    out = out.drop_duplicates().reset_index(drop=True)
    return out


def main():
    parser = argparse.ArgumentParser(description="Extrae alcaldes electos 2015 por municipio (Colombia) desde Wikipedia.")
    parser.add_argument('--url', type=str, default=os.environ.get('ALCALDES_2015_URL'),
                        help='URL de Wikipedia con los resultados por municipio (recomendado usar ?action=render).')
    parser.add_argument('--out', type=str, default=os.path.join('datasets', '02_intermediate', 'alcaldes_2015.csv'),
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