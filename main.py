import flet
from flet import (
    Page, Column, Row, Text, TextField, ElevatedButton, ProgressBar,
    FilePicker, FilePickerResultEvent, FilePickerFileType, icons, SnackBar
)
import threading
import time
import logging
import os
from datetime import datetime

import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# ----------------------------------------------------------------
# Configurar logging
# ----------------------------------------------------------------
logging.basicConfig(
    filename="adidas_scraping.log",
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)

# ----------------------------------------------------------------
# Funciones para cerrar banners y pop-ups
# ----------------------------------------------------------------
def close_cookie_banner(driver):
    try:
        cookie_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.gl-cta--primary'))
        )
        cookie_btn.click()
    except TimeoutException:
        pass
    except Exception as e:
        logging.error(f"Error al cerrar banner de cookies: {e}")

def close_popup(driver):
    try:
        pop_close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.gl-modal__close"))
        )
        pop_close_btn.click()
    except TimeoutException:
        pass
    except Exception as e:
        logging.error(f"Error al cerrar pop-up: {e}")

# ----------------------------------------------------------------
# Función principal de scraping
# ----------------------------------------------------------------
def scrape_code_in_adidas(codigo):
    chrome_options = Options()
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.maximize_window()

    found_name = None
    found_price_normal = None
    found_price_discount = None
    found_model_code = None
    final_url = None

    try:
        # 1) Ir a adidas.cl
        driver.get("https://www.adidas.cl/")
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(2)

        # 2) Cerrar pop-ups
        close_cookie_banner(driver)
        close_popup(driver)

        # 3) Buscar
        search_input = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[data-auto-id="searchinput-desktop"]'))
        )
        search_input.clear()
        search_input.send_keys(codigo)
        search_input.send_keys(Keys.ENTER)

        # 4) Esperar resultados
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'a[data-auto-id="search-product"]'))
        )
        first_product_link = driver.find_element(By.CSS_SELECTOR, 'a[data-auto-id="search-product"]')
        final_url = first_product_link.get_attribute("href")
        first_product_link.click()

        # 5) Esperar en la página de detalle
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(2)

        # Obtener el HTML de la página
        page_html = driver.page_source

        # Guardar HTML para depuración
        with open("page_source.html", "w", encoding="utf-8") as file:
            file.write(page_html)

        # Procesar el HTML con BeautifulSoup
        soup = BeautifulSoup(page_html, "html.parser")

        # Extraer nombre del producto
        title_element = soup.find("h1", {"data-auto-id": "product-title"})
        found_name = title_element.get_text(strip=True) if title_element else "No encontrado"

        # Extraer precios
        normal_price_element = soup.find("div", class_="gl-price-item gl-price-item--crossed notranslate")
        found_price_normal = normal_price_element.get_text(strip=True) if normal_price_element else "No encontrado"

        discount_price_element = soup.find("div", class_="gl-price-item gl-price-item--sale notranslate")
        found_price_discount = discount_price_element.get_text(strip=True) if discount_price_element else "No encontrado"

        # Extraer código de modelo
        model_code_element = soup.find("a", href=True, class_=re.compile(r"variation.*selected"))
        if model_code_element:
            match = re.search(r'/[A-Za-z0-9-]+/([A-Z0-9]{5,})\.html', model_code_element['href'])
            found_model_code = match.group(1) if match else "No encontrado"

        # URL final
        final_url = driver.current_url

    except Exception as e:
        logging.error(f"Error procesando código {codigo}: {e}")
    finally:
        driver.quit()

    return found_name, found_price_normal, found_price_discount, found_model_code, final_url

# ----------------------------------------------------------------
# Guardar en Excel
# ----------------------------------------------------------------
def guardar_excel_adidas(datos):
    df = pd.DataFrame(datos, columns=[
        "Código Ingresado",
        "Nombre",
        "Precio Normal",
        "Precio Descuento",
        "Código Modelo",
        "URL final"
    ])
    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre_archivo = f"Adidas_Scraping_{fecha_hora}.xlsx"
    df.to_excel(nombre_archivo, index=False)
    logging.info(f"Datos guardados en: {nombre_archivo}")
    return nombre_archivo

# ----------------------------------------------------------------
# Interfaz Flet
# ----------------------------------------------------------------
def main(page: flet.Page):
    page.title = "Scraping Adidas (Parsing HTML con BeautifulSoup)"

    stop_event = threading.Event()
    is_running = False
    start_time = [0]

    # UI
    codigos_field = TextField(
        label="Códigos de producto (uno por línea)",
        multiline=True,
        expand=True,
        height=150,
    )
    progress_bar = ProgressBar(value=0, width=400)
    progress_label = Text(value="Progreso: 0%", size=14)
    timer_label = Text(value="Tiempo transcurrido: 00:00", size=12)
    log_text = Text(value="", size=12)

    def actualizar_log(msg: str):
        log_text.value += f"{msg}\n"
        page.update()

    def formatear_tiempo(segundos: int):
        m, s = divmod(segundos, 60)
        return f"{m:02d}:{s:02d}"

    def actualizar_timer(_):
        if is_running:
            elapsed = int(time.time() - start_time[0])
            timer_label.value = f"Tiempo transcurrido: {formatear_tiempo(elapsed)}"
            page.update()

    page.interval = 1000
    page.on_interval = actualizar_timer

    def run_scraping(codigos_list):
        nonlocal is_running
        resultados = []
        total = len(codigos_list)

        actualizar_log("Iniciando scraping...")

        for i, cod_in in enumerate(codigos_list, start=1):
            if stop_event.is_set():
                actualizar_log("Scraping detenido por el usuario.")
                break

            actualizar_log(f"Procesando código {i}/{total}: {cod_in}")

            try:
                name, price_n, price_d, model_code, url_f = scrape_code_in_adidas(cod_in)
            except Exception as e:
                logging.error(f"Error en scrape_code_in_adidas({cod_in}): {e}")
                name = price_n = price_d = model_code = url_f = "Error"

            actualizar_log(f" -> Nombre: {name}")
            actualizar_log(f" -> Precio Normal: {price_n}")
            actualizar_log(f" -> Precio Descuento: {price_d}")
            actualizar_log(f" -> Modelo: {model_code}")
            actualizar_log(f" -> URL: {url_f}")

            resultados.append([cod_in, name, price_n, price_d, model_code, url_f])

            progress = float(i) / float(total)
            progress_bar.value = progress
            progress_label.value = f"Progreso: {int(progress * 100)}%"
            page.update()

        if resultados:
            archivo = guardar_excel_adidas(resultados)
            actualizar_log(f"Resultados guardados en {archivo}")

        is_running = False
        if stop_event.is_set():
            progress_label.value = "Proceso detenido"
        else:
            progress_label.value = "Proceso finalizado"
        page.update()

    def on_iniciar_click(_):
        nonlocal is_running
        if is_running:
            page.snack_bar = SnackBar(Text("Ya hay un proceso en ejecución."), open=True)
            page.update()
            return

        log_text.value = ""
        progress_bar.value = 0
        progress_label.value = "Progreso: 0%"
        timer_label.value = "Tiempo transcurrido: 00:00"
        page.update()

        stop_event.clear()
        is_running = True
        start_time[0] = time.time()

        codigos_str = codigos_field.value.strip()
        if not codigos_str:
            page.snack_bar = SnackBar(Text("No hay códigos ingresados."), open=True)
            page.update()
            is_running = False
            return

        codigos_list = codigos_str.splitlines()

        hilo = threading.Thread(target=run_scraping, args=(codigos_list,), daemon=True)
        hilo.start()

    def on_detener_click(_):
        if not is_running:
            page.snack_bar = SnackBar(Text("No hay proceso en ejecución."), open=True)
            page.update()
            return
        stop_event.set()

    def on_file_picked(e: FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            if file_path and os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        contenido = f.read()
                    codigos_field.value = contenido
                    page.snack_bar = SnackBar(Text(f"Archivo cargado: {file_path}"), open=True)
                except Exception as ex:
                    page.snack_bar = SnackBar(Text(f"Error al leer archivo: {ex}"), open=True)
            else:
                page.snack_bar = SnackBar(Text("Archivo no válido."), open=True)
        page.update()

    file_picker = FilePicker(on_result=on_file_picked)

    page.add(
        file_picker,
        Column(
            controls=[
                Text("Scraping Adidas (Parsing HTML con BeautifulSoup)", size=18, weight="bold"),
                Text("1) Ingresa códigos o carga un archivo con códigos."),
                Row(
                    controls=[
                        ElevatedButton(
                            "Cargar archivo",
                            icon=icons.UPLOAD_FILE,
                            on_click=lambda _: file_picker.pick_files(
                                allow_multiple=False,
                                file_type=FilePickerFileType.ANY
                            )
                        )
                    ]
                ),
                codigos_field,
                Row(
                    controls=[
                        ElevatedButton("Iniciar", icon=icons.PLAY_ARROW, on_click=on_iniciar_click),
                        ElevatedButton("Detener", icon=icons.STOP, on_click=on_detener_click),
                    ]
                ),
                progress_bar,
                progress_label,
                timer_label,
                Text("Log de proceso:", size=14, weight="bold"),
                log_text
            ],
            scroll="auto",
            expand=True
        )
    )

# ----------------------------------------------------------------
# Ejecutar la app
# ----------------------------------------------------------------
if __name__ == "__main__":
    flet.app(target=main, view=flet.FLET_APP)
