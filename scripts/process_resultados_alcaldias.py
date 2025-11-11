import pandas as pd
from pathlib import Path
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_electoral_results(year: str = "2019"):
    """
    Procesa los resultados electorales de alcaldías por año.
    
    Args:
        year: Año de las elecciones (default: "2019")
    """
    # Directorios
    raw_dir = Path("datasets/01_raw")
    intermediate_dir = Path("datasets/02_intermediate")
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    
    # Buscar todos los archivos de resultados del año especificado
    pattern = f"resultados_*_{year}.csv"
    result_files = list(raw_dir.glob(pattern))
    
    if not result_files:
        logger.error(f"No se encontraron archivos de resultados para el año {year}")
        return
    
    logger.info(f"Encontrados {len(result_files)} archivos de resultados para {year}")
    
    # Lista para almacenar los dataframes procesados
    all_results = []
    
    # Procesar cada archivo de departamento
    for file_path in tqdm(result_files, desc="Procesando departamentos"):
        try:
            logger.info(f"Procesando: {file_path.name}")
            
            # Leer el archivo CSV
            df = pd.read_csv(file_path)
            
            # Verificar que las columnas necesarias existan
            required_columns = [
                'Nombre Corporación', 
                'Nombre Candidato', 
                'Total Votos',
                'Nombre Departamento',
                'Nombre Municipio'
            ]
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.warning(f"Columnas faltantes en {file_path.name}: {missing_columns}")
                continue
            
            # Filtrar solo alcaldías (puede ser "ALCALDE" o "ALCALDÍA")
            df_alcaldia = df[
                df['Nombre Corporación'].str.upper().str.contains('ALCALDE|ALCALDÍA|ALCALDIA', na=False)
            ].copy()
            
            if df_alcaldia.empty:
                logger.warning(f"No se encontraron datos de alcaldía en {file_path.name}")
                continue
            
            logger.info(f"  Registros de alcaldía: {len(df_alcaldia)}")
            
            # Eliminar votos no válidos
            votos_excluir = ['VOTOS NO MARCADOS', 'VOTOS EN BLANCO', 'VOTOS NULOS']
            df_filtered = df_alcaldia[
                ~df_alcaldia['Nombre Candidato'].isin(votos_excluir)
            ].copy()
            
            logger.info(f"  Registros después de filtrar votos no válidos: {len(df_filtered)}")
            
            if df_filtered.empty:
                logger.warning(f"No hay datos válidos después de filtrar en {file_path.name}")
                continue
            
            # Agrupar por Departamento, Municipio y Candidato, sumando los votos
            df_grouped = df_filtered.groupby(
                [
                    'Código Departamento',
                    'Nombre Departamento',
                    'Código Municipio', 
                    'Nombre Municipio',
                    'Nombre Candidato',
                    'Código Partido',
                    'Nombre Partido'
                ],
                as_index=False
            )['Total Votos'].sum()
            
            logger.info(f"  Candidatos únicos: {df_grouped['Nombre Candidato'].nunique()}")
            
            # Obtener los top 2 candidatos por municipio
            top_candidates = (
                df_grouped
                .sort_values(['Código Municipio', 'Total Votos'], ascending=[True, False])
                .groupby(['Código Municipio', 'Nombre Municipio'])
                .head(2)
                .reset_index(drop=True)
            )
            
            logger.info(f"  Municipios procesados: {top_candidates['Nombre Municipio'].nunique()}")
            logger.info(f"  Registros finales (top 2 por municipio): {len(top_candidates)}")
            
            # Agregar el año
            top_candidates['Año'] = year
            
            all_results.append(top_candidates)
            
        except Exception as e:
            logger.error(f"Error procesando {file_path.name}: {e}")
            continue
    
    # Verificar que hay resultados para combinar
    if not all_results:
        logger.error("No se procesaron resultados exitosamente")
        return
    
    # Combinar todos los resultados
    logger.info(f"\nCombinando resultados de {len(all_results)} departamentos...")
    final_df = pd.concat(all_results, ignore_index=True)
    
    # Ordenar por departamento, municipio y votos (descendente)
    final_df = final_df.sort_values(
        ['Nombre Departamento', 'Nombre Municipio', 'Total Votos'],
        ascending=[True, True, False]
    ).reset_index(drop=True)
    
    # Guardar el resultado
    output_file = intermediate_dir / "resultados_electorales_intermediate.csv"
    final_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    # Resumen
    logger.info(f"\n{'='*60}")
    logger.info(f"RESUMEN DEL PROCESAMIENTO")
    logger.info(f"{'='*60}")
    logger.info(f"Total de registros: {len(final_df):,}")
    logger.info(f"Departamentos únicos: {final_df['Nombre Departamento'].nunique()}")
    logger.info(f"Municipios únicos: {final_df['Nombre Municipio'].nunique()}")
    logger.info(f"Candidatos únicos: {final_df['Nombre Candidato'].nunique()}")
    logger.info(f"Total de votos: {final_df['Total Votos'].sum():,}")
    logger.info(f"\nArchivo guardado: {output_file}")
    logger.info(f"{'='*60}")
    
    # Mostrar ejemplo de los primeros registros
    logger.info(f"\nPrimeros registros:")
    print(final_df.head(10).to_string())
    
    # Mostrar estadísticas por departamento
    logger.info(f"\nRegistros por departamento:")
    dept_counts = final_df.groupby('Nombre Departamento').size().sort_values(ascending=False)
    print(dept_counts.to_string())


def main():
    """Main execution function"""
    logger.info("Iniciando procesamiento de resultados electorales de alcaldías...")
    process_electoral_results(year="2019")
    logger.info("\nProcesamiento completado!")


if __name__ == "__main__":
    main()

