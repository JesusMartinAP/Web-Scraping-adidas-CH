import flet
from flet import (
    Page, Column, Row, Text, TextField, ElevatedButton, ProgressBar,
    FilePicker, FilePickerResultEvent, FilePickerFileType, icons, SnackBar
)
import threading
import time
import logging
import os
import re
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

# Para instalar el driver automáticamente:
from webdriver_manager.chrome import ChromeDriverManager

# ----------------------------------------------------------------
# Configurar logging (útil cuando empaquetas con PyInstaller)
# ----------------------------------------------------------------
logging.basicConfig(
    filename="adidas_scraping.log",
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)

# ----------------------------------------------------------------
# 1) Cerrar banners de cookies y pop-ups
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
# 2) Expresiones regulares para extraer nombre y precio del texto
# ----------------------------------------------------------------
def parse_name_price_from_text(full_text):
    """
    Busca EXACTAMENTE "Camiseta Local Universidad de Chile 2025"
    y la primera coincidencia de precio con formato $59.990, etc.
    Ajusta si tu producto y precio son diferentes.
    """
    name_pattern = r"(Camiseta Local Universidad de Chile 2025)"
    price_pattern = r"\$\d{1,3}(\.\d{3})*(,\d+)?"

    found_name = None
    found_price = None

    match_name = re.search(name_pattern, full_text)
    if match_name:
        found_name = match_name.group(1)

    match_price = re.search(price_pattern, full_text)
    if match_price:
        found_price = match_price.group(0)

    return found_name, found_price

# ----------------------------------------------------------------
# 3) Scraping principal
# ----------------------------------------------------------------
def scrape_code_in_adidas(codigo):
    """
    Flujo:
      1) Abre "https://www.adidas.cl"
      2) Cierra banner y pop-up
      3) Pega 'codigo' en input[data-auto-id="searchinput-desktop"], Enter
      4) Clic en primer producto
      5) En la página de detalle, hace:
          - Ctrl + A (seleccionar todo)
          - F6 (como si fuera a la barra de direcciones)
          - Toma body.text
        y con RegEx extrae nombre y precio
      6) Retorna (found_name, found_price, driver.current_url)
    """
    chrome_options = Options()
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Maximizar la ventana para evitar problemas de diseño responsivo
    driver.maximize_window()

    found_name = None
    found_price = None
    final_url = None

    try:
        # 1) Ir a adidas.cl
        driver.get("https://www.adidas.cl/")
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(2)

        # 2) Cerrar pop-ups
        close_cookie_banner(driver)
        close_popup(driver)

        # 3) Localizar campo de búsqueda
        search_input = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[data-auto-id="searchinput-desktop"]'))
        )
        search_input.clear()
        search_input.send_keys(codigo)
        search_input.send_keys(Keys.ENTER)

        # 4) Esperar primer producto y hacer click
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'a[data-auto-id="search-product"]'))
        )
        first_product_link = driver.find_element(By.CSS_SELECTOR, 'a[data-auto-id="search-product"]')
        final_url = first_product_link.get_attribute("href")
        first_product_link.click()

        # 5) Esperar la página de detalle
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(2)

        # Ahora sí: Ctrl + A y luego F6
        body_elem = driver.find_element(By.TAG_NAME, 'body')
        # Enviar Ctrl + A
        body_elem.send_keys(Keys.CONTROL, 'a')
        time.sleep(1)
        # Enviar F6
        body_elem.send_keys(Keys.F6)
        time.sleep(1)

        # Capturar todo el texto
        full_text = driver.find_element(By.TAG_NAME, 'body').text
        # Regex
        found_name, found_price = parse_name_price_from_text(full_text)

        # URL final (equivale a "F6" + "copiar" la URL, pero Selenium la obtiene directamente)
        final_url = driver.current_url

    except Exception as e:
        logging.error(f"Error procesando código {codigo}: {e}")
    finally:
        driver.quit()

    return found_name, found_price, final_url

# ----------------------------------------------------------------
# 4) Guardar en Excel
# ----------------------------------------------------------------
def guardar_excel_adidas(datos):
    df = pd.DataFrame(datos, columns=["Código", "Nombre", "Precio", "URL final"])
    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre_archivo = f"Adidas_Scraping_{fecha_hora}.xlsx"
    df.to_excel(nombre_archivo, index=False)
    logging.info(f"Datos guardados en: {nombre_archivo}")
    return nombre_archivo

# ----------------------------------------------------------------
# 5) Interfaz Flet
# ----------------------------------------------------------------
def main(page: flet.Page):
    page.title = "Scraping Adidas - CTRL+A y F6 (RegEx en texto completo)"

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

        for i, codigo in enumerate(codigos_list, start=1):
            if stop_event.is_set():
                actualizar_log("Scraping detenido por el usuario.")
                break

            actualizar_log(f"Procesando código {i}/{total}: {codigo}")

            try:
                found_name, found_price, final_url = scrape_code_in_adidas(codigo)
            except Exception as e:
                logging.error(f"Error en scrape_code_in_adidas({codigo}): {e}")
                found_name = "Error"
                found_price = "Error"
                final_url = "Error"

            actualizar_log(f" - Nombre: {found_name}")
            actualizar_log(f" - Precio: {found_price}")
            actualizar_log(f" - URL: {final_url}")

            if not found_name:
                found_name = "No se encontró"
            if not found_price:
                found_price = "No se encontró"
            if not final_url:
                final_url = "No se obtuvo URL"

            resultados.append([codigo, found_name, found_price, final_url])

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
                Text("Scraping Adidas - CTRL+A y F6 (RegEx en texto completo)", size=18, weight="bold"),
                Text("1) Ingresa tus códigos (uno por línea) o carga un .txt."),
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
# 6) Ejecutar la app
# ----------------------------------------------------------------
if __name__ == "__main__":
    # Para empaquetar con PyInstaller y abrir en ventana nativa:
    flet.app(target=main, view=flet.FLET_APP)
