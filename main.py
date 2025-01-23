import flet
from flet import (
    Page, Column, Row, Text, TextField, ElevatedButton, ProgressBar,
    FilePicker, FilePickerResultEvent, FilePickerFileType,
    icons, SnackBar
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
# Cerrar banner de cookies
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

# ----------------------------------------------------------------
# Cerrar pop-up
# ----------------------------------------------------------------
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
# Scraping principal
# ----------------------------------------------------------------
def scrape_code_in_adidas(codigo):
    """
    Flujo:
      1. Abrir adidas.cl
      2. Cerrar banner cookies y pop-up
      3. Pegar el código en input[data-auto-id="searchinput-desktop"], Enter
      4. Esperar resultados -> a[data-auto-id="search-product"]
      5. Clic en primer producto -> Detalle
      6. Extraer:
         - Nombre: <h1 data-auto-id="product-title"> <span>...</span> </h1>
         - Precios (div.gl-price.gl-price--horizontal.notranslate[data-auto-id="gl-price-item"])
           * .gl-price-item--crossed => precio normal
           * .gl-price-item--sale => precio oferta
    """

    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    product_name = None
    regular_price = None
    sale_price = None
    final_url = None

    try:
        # 1) Ir a adidas.cl
        driver.get("https://www.adidas.cl/")
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(2)

        # 2) Cerrar banner cookies y pop-up
        close_cookie_banner(driver)
        close_popup(driver)

        # 3) Input desktop (pegar código y Enter)
        search_input = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[data-auto-id="searchinput-desktop"]'))
        )
        search_input.clear()
        search_input.send_keys(codigo)
        search_input.send_keys(Keys.ENTER)

        # 4) Esperar la lista de resultados (sugerencias o la búsqueda) con data-auto-id="search-product"
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'a[data-auto-id="search-product"]'))
        )

        # Tomar el primer producto
        first_product_link = driver.find_element(By.CSS_SELECTOR, 'a[data-auto-id="search-product"]')
        final_url = first_product_link.get_attribute("href")
        first_product_link.click()

        # 5) Esperar la página de detalle y extraer nombre
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'h1[data-auto-id="product-title"] span'))
        )
        time.sleep(2)  # Pequeña pausa extra

        # Nombre del producto
        product_name = driver.find_element(By.CSS_SELECTOR, 'h1[data-auto-id="product-title"] span').text

        # 6) Extraer precios
        #    <div class="gl-price gl-price--horizontal notranslate" data-auto-id="gl-price-item">
        #       <div class="gl-price-item gl-price-item--crossed notranslate">$169.990</div>
        #       <div class="gl-price-item gl-price-item--sale notranslate">$101.990</div>
        #    </div>
        price_block = driver.find_element(By.CSS_SELECTOR, 'div.gl-price.gl-price--horizontal.notranslate[data-auto-id="gl-price-item"]')
        price_items = price_block.find_elements(By.CSS_SELECTOR, 'div.gl-price-item')

        for p_item in price_items:
            classes = p_item.get_attribute("class")
            price_text = p_item.text.strip()
            if "gl-price-item--crossed" in classes:
                regular_price = price_text
            elif "gl-price-item--sale" in classes:
                sale_price = price_text
            else:
                # Si no tiene ni crossed ni sale, puede ser que sea el único precio disponible
                if not regular_price:
                    regular_price = price_text

        final_url = driver.current_url

    except Exception as e:
        logging.error(f"Error procesando código {codigo}: {e}")
    finally:
        driver.quit()

    return product_name, regular_price, sale_price, final_url

# ----------------------------------------------------------------
# Guardar en Excel
# ----------------------------------------------------------------
def guardar_excel_adidas(datos):
    """
    datos: lista de [codigo, nombre, precio_normal, precio_descuento, url]
    """
    df = pd.DataFrame(datos, columns=[
        "Código",
        "Nombre",
        "Precio Normal",
        "Precio Descuento",
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
def main(page: Page):
    page.title = "Scraping Adidas - Flet (Nuevos Selectores: h1 y gl-price)"

    stop_event = threading.Event()  # Para detener
    is_running = False
    start_time = [0]

    # ----------------------------------------
    # Elementos de la UI
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
    # Funciones de ayuda
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
    # Lógica de scraping (en un hilo)
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
                nombre, precio_normal, precio_descuento, url_final = scrape_code_in_adidas(codigo)
            except Exception as e:
                logging.error(f"Error en scrape_code_in_adidas({codigo}): {e}")
                nombre = precio_normal = precio_descuento = url_final = "Error"

            if not nombre:
                nombre = "No se encontró"
            if not precio_normal:
                precio_normal = "No se encontró"
            if not precio_descuento:
                precio_descuento = "No se encontró"
            if not url_final:
                url_final = "No se obtuvo URL"

            resultados.append([codigo, nombre, precio_normal, precio_descuento, url_final])

            # Barra de progreso
            progress = float(i) / float(total)
            progress_bar.value = progress
            progress_label.value = f"Progreso: {int(progress * 100)}%"
            page.update()

        # Guardar en Excel
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

        # Obtener lista de códigos
        codigos_str = codigos_field.value.strip()
        if not codigos_str:
            page.snack_bar = SnackBar(Text("No hay códigos ingresados."), open=True)
            page.update()
            is_running = False
            return

        codigos_list = codigos_str.splitlines()

        # Iniciar hilo
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
                Text("Scraping Adidas - Flet (Nuevos Selectores: h1 y gl-price)", size=18, weight="bold"),
                Text("1) Ingresa tus códigos o carga un archivo .txt"),
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
    # Para empaquetar con PyInstaller y abrir en ventana nativa:
    flet.app(target=main, view=flet.FLET_APP)
