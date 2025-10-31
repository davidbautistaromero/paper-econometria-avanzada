import os
import time
import unicodedata
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://observatorio.registraduria.gov.co/views/electoral/historicos-resultados.php"
BASE_DOMAIN = "https://observatorio.registraduria.gov.co"

YEARS = ["2019", "2023"]  # Años a iterar
YEAR_SELECT = "#anconsulta"
# Selectores pueden variar según el año
DEPARTMENT_SELECTS = ["#departmentSelect2", "#departmentSelect", "select[name='department']"]
DOWNLOAD_ANCHORS = ["#downloadLink2", "#downloadLink", "a.download-link"]

OUT_BASE = Path("datasets/01_raw")  # Carpeta raíz de salida


def slugify(value: str) -> str:
    """
    Convierte un texto a un slug seguro para paths.
    Elimina acentos, caracteres especiales y espacios múltiples.
    """
    value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    value = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value)
    value = "-".join(filter(None, value.split("-")))
    return value.lower()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def extract_and_cleanup_zip(zip_path: Path, year: str, department: str) -> bool:
    """
    Extrae el archivo CSV del ZIP, lo guarda con nombre apropiado y elimina el ZIP.
    
    Args:
        zip_path: Ruta del archivo ZIP descargado
        year: Año del resultado electoral
        department: Nombre del departamento (slug)
    
    Returns:
        True si la extracción fue exitosa, False en caso contrario
    """
    try:
        print(f"    Extrayendo archivo ZIP...")
        
        # Abrir el archivo ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Listar archivos en el ZIP
            file_list = zip_ref.namelist()
            print(f"    Archivos en ZIP: {file_list}")
            
            # Buscar el archivo CSV (puede haber varios)
            csv_files = [f for f in file_list if f.lower().endswith('.csv')]
            
            if not csv_files:
                print(f"    [WARN] No se encontró archivo CSV en el ZIP")
                return False
            
            # Si hay múltiples CSVs, usar el primero o el que parezca más relevante
            csv_file = csv_files[0]
            if len(csv_files) > 1:
                print(f"    [INFO] Múltiples CSVs encontrados, usando: {csv_file}")
            
            # Crear nombre para el archivo CSV extraído
            csv_output_path = zip_path.parent / f"resultados_{department}_{year}.csv"
            
            # Extraer el CSV
            with zip_ref.open(csv_file) as source, open(csv_output_path, 'wb') as target:
                target.write(source.read())
            
            print(f"    [OK] CSV extraído: {csv_output_path.name}")
        
        # Eliminar el archivo ZIP
        zip_path.unlink()
        print(f"    [OK] Archivo ZIP eliminado")
        
        return True
        
    except zipfile.BadZipFile:
        print(f"    [ERROR] El archivo ZIP está corrupto")
        return False
    except Exception as e:
        print(f"    [ERROR] Error al extraer ZIP: {e}")
        return False


def main(headless: bool = True, pause_between_downloads_sec: float = 0.5):
    ensure_dir(OUT_BASE)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("Cargando página...")
        # Ir a la página
        page.goto(BASE_URL, wait_until="domcontentloaded")
        
        # Esperar más tiempo para que la página cargue completamente
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            print("[WARN] La página no alcanzó estado 'networkidle', continuando de todos modos...")
        
        # Espera adicional para asegurar que el JavaScript se ejecute
        page.wait_for_timeout(3000)
        
        # Verificar que el selector del año existe
        try:
            page.wait_for_selector(YEAR_SELECT, state="visible", timeout=15000)
            print(f"Selector de año encontrado: {YEAR_SELECT}")
        except PlaywrightTimeoutError:
            print(f"[ERROR] No se encontró el selector de año: {YEAR_SELECT}")
            print("Selectores disponibles en la página:")
            selects = page.eval_on_selector_all("select", "els => els.map(e => e.id || e.name || e.className)")
            print(f"  Selects encontrados: {selects}")
            browser.close()
            return

        for year in YEARS:
            print(f"\n=== Procesando año {year} ===")

            # Seleccionar el año
            try:
                page.select_option(YEAR_SELECT, year)
                print(f"Año {year} seleccionado correctamente")
            except Exception as e:
                print(f"[ERROR] No se pudo seleccionar el año {year}: {e}")
                continue
            
            # Pequeña espera por si hay JS que actualiza DOM/href
            page.wait_for_timeout(1500)

            # Detectar el selector de departamento que existe
            dept_select = None
            for selector in DEPARTMENT_SELECTS:
                try:
                    page.locator(selector).wait_for(state="visible", timeout=3000)
                    dept_select = selector
                    print(f"Selector de departamento encontrado: {selector}")
                    break
                except PlaywrightTimeoutError:
                    continue
            
            if not dept_select:
                print(f"[WARN] No se encontró ningún select de departamentos para el año {year}.")
                print("Selectores disponibles:")
                selects = page.eval_on_selector_all("select", "els => els.map(e => '#' + (e.id || 'sin-id') + ' (' + (e.name || 'sin-name') + ')')")
                print(f"  {selects}")
                continue
            
            # Detectar el enlace de descarga que existe
            download_anchor = None
            for selector in DOWNLOAD_ANCHORS:
                try:
                    if page.locator(selector).count() > 0:
                        download_anchor = selector
                        print(f"Enlace de descarga encontrado: {selector}")
                        break
                except:
                    continue
            
            if not download_anchor:
                print(f"[WARN] No se encontró el enlace de descarga para el año {year}.")
                continue

            # Leer todas las opciones del select
            options = page.eval_on_selector_all(
                f"{dept_select} option",
                "els => els.map(e => ({value: e.value, label: (e.textContent || '').trim()}))"
            )

            # Filtrar opciones válidas (no vacías) y excluir COLOMBIA
            valid_options = [
                o for o in options
                if o.get("value") and o.get("label") and o["label"].strip().upper() != "COLOMBIA"
            ]

            print(f"Departamentos a descargar en {year}: {len(valid_options)}")

            for opt in valid_options:
                dept_value = opt["value"]
                dept_label = opt["label"]
                safe_label = slugify(dept_label)
                
                # Verificar si ya existe el CSV final
                csv_path = OUT_BASE / f"resultados_{safe_label}_{year}.csv"
                if csv_path.exists():
                    print(f"[SKIP] Ya existe: {csv_path.name}")
                    continue
                
                # Formato temporal: resultados_departamento_año.zip (los archivos son ZIP)
                target_path = OUT_BASE / f"resultados_{safe_label}_{year}.zip"

                print(f"  - {dept_label} (value={dept_value}) -> {csv_path.name}")

                # Seleccionar departamento
                try:
                    page.select_option(dept_select, dept_value)
                    print(f"    Departamento seleccionado, esperando actualización...")
                except Exception as e:
                    print(f"    [ERROR] No se pudo seleccionar {dept_label}: {e}")
                    continue

                # Esperar más tiempo para que el JavaScript actualice el enlace
                page.wait_for_timeout(2000)

                # Esperar a que el link de descarga tenga href válido
                try:
                    page.wait_for_function(
                        """(selector) => {
                            const a = document.querySelector(selector);
                            return a && a.getAttribute('href') && a.getAttribute('href') !== '#';
                        }""",
                        arg=download_anchor,
                        timeout=10000
                    )
                    print(f"    Enlace de descarga listo")
                except PlaywrightTimeoutError:
                    print("    [WARN] El enlace de descarga no se actualizó. Intentando de todos modos...")
                except Exception as e:
                    print(f"    [WARN] Error verificando enlace: {e}")

                # Obtener el href y construir URL completa
                try:
                    href = page.evaluate(f"document.querySelector('{download_anchor}')?.getAttribute('href')")
                    print(f"    href relativo: {href}")
                    
                    if href:
                        # Construir URL absoluta
                        if href.startswith('http'):
                            full_url = href
                        else:
                            full_url = BASE_DOMAIN + href
                        
                        print(f"    Descargando desde: {full_url}")
                        
                        # Descargar directamente con requests
                        import requests
                        response = requests.get(full_url, timeout=60, stream=True)
                        
                        if response.status_code == 200:
                            ensure_dir(target_path.parent)
                            # Descargar con progreso
                            total_size = int(response.headers.get('content-length', 0))
                            with open(target_path, 'wb') as f:
                                if total_size > 0:
                                    downloaded = 0
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                            downloaded += len(chunk)
                                            progress = (downloaded / total_size) * 100
                                            print(f"\r    Progreso: {progress:.1f}%", end='', flush=True)
                                    print()  # Nueva línea
                                else:
                                    f.write(response.content)
                            
                            print(f"    [OK] Descarga exitosa: {target_path}")
                            
                            # Extraer el CSV del ZIP y eliminar el ZIP
                            extract_and_cleanup_zip(target_path, year, safe_label)
                        else:
                            print(f"    [ERROR] Error en descarga: HTTP {response.status_code}")
                    else:
                        print(f"    [ERROR] No se pudo obtener el href del enlace")
                        
                except Exception as e:
                    print(f"    [ERROR] Falló la descarga: {e}")

                # Templar la cadencia para no saturar el servidor
                time.sleep(pause_between_downloads_sec)

        context.close()
        browser.close()


if __name__ == "__main__":
    # headless=False para ver el navegador (útil para debug)
    # headless=True para modo invisible
    main(headless=False, pause_between_downloads_sec=0.8)