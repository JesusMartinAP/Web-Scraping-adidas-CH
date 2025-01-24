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

from webdriver_manager.chrome import ChromeDriverManager


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
# 1) Funciones genéricas para cerrar banners
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
# 2) Extraer nombre y precio usando RegEx en todo el texto
# ----------------------------------------------------------------
def parse_name_price_from_text(full_text):
    """
    Ajusta los patrones según tus necesidades reales.
    Aquí usamos ejemplos directos:
      - Nombre fijo: "Camiseta Local Universidad de Chile 2025"
      - Precio: formato como "$59.990", "$101.990", etc.
    """
    name_pattern = r"(Camiseta Local Universidad de Chile 2025)"
    price_pattern = r"\$\d{1,3}(\.\d{3})*(,\d+)?"

    found_name = None
    found_price = None

    # Buscar el nombre exacto (puedes usar una regex más amplia)
    match_name = re.search(name_pattern, full_text)
    if match_name:
        found_name = match_name.group(1)

    # Buscar el primer precio (puedes ajustar si hay varios)
    match_price = re.search(price_pattern, full_text)
    if match_price:
        found_price = match_price.group(0)

    return found_name, found_price


# ----------------------------------------------------------------
# 3) Scraping principal con Selenium + RegEx
# ----------------------------------------------------------------
def scrape_code_in_adidas(codigo):
    """
    Flujo:
      1) Ir a adidas.cl
      2) Cerrar pop-ups
      3) Buscar el 'codigo' en input[data-auto-id="searchinput-desktop"], Enter
      4) Clic en el primer resultado
      5) Seleccionar todo el texto del <body> (o simplemente body.text)
      6) Usar RegEx para extraer:
         - Nombre: "Camiseta Local Universidad de Chile 2025" (ejemplo)
         - Precio: "$59.990" (ejemplo)
      7) La URL final es driver.current_url
    """

    chrome_options = Options()
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Maximizamos la ventana (por si la vista "responsive" oculta algo)
    driver.maximize_window()

    found_name = None
    found_price = None
    final_url = None

    try:
        # 1) Ir a adidas.cl
        driver.get("https://www.adidas.cl/")
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(2)

        # 2) Cerrar banners
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

        # 5) Esperar página de detalle
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(2)

        # "Ctrl + A" es para seleccionar todo, pero no necesitas mandar keys:
        # con driver.find_element(By.TAG_NAME, 'body').text ya obtienes todo el texto.
        full_text = driver.find_element(By.TAG_NAME, 'body').text

        # 6) RegEx
        found_name, found_price = parse_name_price_from_text(full_text)

        # 7) URL final
        final_url = driver.current_url

    except Exception as e:
        logging.error(f"Error procesando código {codigo}: {e}")
    finally:
        driver.quit()

    return found_name, found_price, final_url


# ----------------------------------------------------------------
# 4) Guardar Excel
# ----------------------------------------------------------------
def guardar_excel_adidas(datos):
    """
    datos: lista de [codigo, nombre, precio, url]
    """
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
    page.title = "Scraping Adidas - Flet con RegEx en texto completo"

    stop_event = threading.Event()
    is_running = False
    start_time = [0]

    # ----------------------------------------
    # Elementos UI
    # ----------------------------------------
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

    # ----------------------------------------
    # Funciones de apoyo
    # ----------------------------------------
    def actualizar_log(msg: str):
        log_text.value += f"{msg}\n"
        page.update()

    def formatear_tiempo(segundos: int):
        m, s = divmod(segundos, 60)
        return f"{m:02d}:{s:02d}"

    # ----------------------------------------
    # Timer
    # ----------------------------------------
    def actualizar_timer(_):
        if is_running:
            elapsed = int(time.time() - start_time[0])
            timer_label.value = f"Tiempo transcurrido: {formatear_tiempo(elapsed)}"
            page.update()

    page.interval = 1000
    page.on_interval = actualizar_timer

    # ----------------------------------------
    # Lógica de scraping en hilo
    # ----------------------------------------
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

            if not found_name:
                found_name = "No se encontró"
            if not found_price:
                found_price = "No se encontró"
            if not final_url:
                final_url = "No se obtuvo URL"

            resultados.append([codigo, found_name, found_price, final_url])

            # Barra de progreso
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

    # ----------------------------------------
    # Botones
    # ----------------------------------------
    def on_iniciar_click(_):
        nonlocal is_running
        if is_running:
            page.snack_bar = SnackBar(Text("Ya hay un proceso en ejecución."), open=True)
            page.update()
            return

        # Resetear interfaz
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

    # ----------------------------------------
    # FilePicker (opcional)
    # ----------------------------------------
    def on_file_picked(e: FilePickerResultEvent):
        if e.files is not None and len(e.files) > 0:
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

    # ----------------------------------------
    # Layout principal
    # ----------------------------------------
    page.add(
        file_picker,
        Column(
            controls=[
                Text("Scraping Adidas - Flet + RegEx en texto completo", size=18, weight="bold"),
                Text("1) Pega los códigos o carga un archivo con códigos."),
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
