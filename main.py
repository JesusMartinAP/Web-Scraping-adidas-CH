import flet
from flet import (
    Page,
    Column,
    Row,
    Text,
    TextField,
    ElevatedButton,
    ProgressBar,
    FilePicker,
    FilePickerResultEvent,
    FilePickerFileType,
    icons,
    SnackBar
)
import threading
import time
import logging
import os
from datetime import datetime
import pandas as pd
import re

import pyperclip
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(
    filename="adidas_scraping.log",
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)

# ----------------------------------------------------------------
# 1) Funciones para cerrar banners y pop-ups
# ----------------------------------------------------------------
def close_cookie_banner(driver):
    try:
        cookie_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.gl-cta--primary'))
        )
        cookie_btn.click()
        logging.info("Banner de cookies cerrado.")
    except:
        logging.info("No se pudo cerrar banner (o no existía).")

def close_popup(driver):
    try:
        pop_close_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.gl-modal__close"))
        )
        pop_close_btn.click()
        logging.info("Pop-up cerrado.")
    except:
        logging.info("No se encontró pop-up (o no se pudo cerrar).")


# ----------------------------------------------------------------
# 2) Función que simula Ctrl+A / Ctrl+C y obtiene todo el texto
# ----------------------------------------------------------------
def copy_page_text_like_human(driver):
    """
    Da clic en <body>, luego CTRL+A y CTRL+C,
    y finalmente retorna el contenido del portapapeles (texto).
    """
    body = driver.find_element(By.TAG_NAME, "body")
    body.click()
    time.sleep(1)

    actions = ActionChains(driver)
    # Ctrl + A
    actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
    time.sleep(1)
    # Ctrl + C
    actions.key_down(Keys.CONTROL).send_keys("c").key_up(Keys.CONTROL).perform()
    time.sleep(1)

    copied_text = pyperclip.paste()
    return copied_text

# ----------------------------------------------------------------
# 3) Función principal de scraping: "scrape_like_human"
# ----------------------------------------------------------------
def scrape_like_human(codigo):
    """
    - Abre Adidas Chile
    - Cierra banner/popup
    - Busca el SKU "codigo"
    - Si hay página de resultados, clic en el primero
    - CTRL+A, CTRL+C -> texto
    Retorna (url_final, texto_copiado).
    """
    chrome_options = Options()
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.maximize_window()

    product_text = ""
    final_url = ""

    try:
        driver.get("https://www.adidas.cl/")
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)

        close_cookie_banner(driver)
        close_popup(driver)

        # Buscar el código
        search_input = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[data-auto-id="searchinput-desktop"]'))
        )
        logging.info(f"Buscando SKU: {codigo}")
        search_input.clear()
        search_input.send_keys(codigo)
        search_input.send_keys(Keys.ENTER)
        time.sleep(2)

        current_url = driver.current_url
        logging.info(f"URL tras buscar: {current_url}")

        # Ver si hay lista de resultados
        links = driver.find_elements(By.CSS_SELECTOR, 'a[data-auto-id="search-product"]')
        if len(links) > 0:
            logging.info("Hay lista de resultados, clic en el primero.")
            first_link = links[0]
            final_url = first_link.get_attribute("href")
            first_link.click()
            time.sleep(2)
            # A veces abre otra pestaña
            handles = driver.window_handles
            logging.info(f"Ventanas actuales: {handles}")
            driver.switch_to.window(handles[-1])
            time.sleep(2)
        else:
            logging.info("Asumimos que ya estamos en la página del producto.")
            final_url = driver.current_url

        # Asegurarse de que la página cargó
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)

        # Copiar texto
        product_text = copy_page_text_like_human(driver)
        logging.info(f"Longitud del texto copiado: {len(product_text)}")

        final_url = driver.current_url

    except Exception as e:
        logging.error(f"Error procesando código {codigo}: {e}")

    finally:
        driver.quit()

    return final_url, product_text


# ----------------------------------------------------------------
# 4) Lógicas para extraer nombre y precios (normal, descuento)
# ----------------------------------------------------------------
def parse_by_numeric_marker(lines):
    """
    Lógica A: busca la primera línea que sea SOLO dígitos (e.g. "27" o "1").
    La siguiente línea no vacía => nombre
    Luego, 1 o 2 líneas que empiecen con '$' => precio normal, precio descuento.
    """
    patron_digitos = re.compile(r'^\d+$')
    patron_precio = re.compile(r'^\$\d[\d\.,]*')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if patron_digitos.match(line):
            # Buscar nombre
            i += 1
            nombre = None
            while i < len(lines):
                nombre_candidate = lines[i].strip()
                if nombre_candidate:
                    nombre = nombre_candidate
                    break
                i += 1
            if not nombre:
                return None, None, None

            i += 1
            precios = []
            while i < len(lines):
                posible_precio = lines[i].strip()
                if patron_precio.match(posible_precio):
                    precios.append(posible_precio)
                elif posible_precio and not patron_precio.match(posible_precio):
                    break
                i += 1

            if len(precios) == 0:
                return None, None, None

            precio_normal = precios[0]
            precio_descuento = precios[1] if len(precios) > 1 else None
            return nombre, precio_normal, precio_descuento
        i += 1

    return None, None, None


def parse_by_category_marker(lines):
    """
    Lógica B: busca línea con "Hombre •", "Mujer •", "Niñ(o/a)s •", "Unisex •"
    Luego, siguiente línea no vacía => nombre
    Luego, líneas con '$' => precios
    """
    patron_categoria = re.compile(r'^(hombre|mujer|niñ[oa]s|unisex)\s*•', re.IGNORECASE)
    patron_precio = re.compile(r'^\$\d[\d\.,]*')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if patron_categoria.search(line):
            i += 1
            nombre = None
            while i < len(lines):
                nombre_candidate = lines[i].strip()
                if nombre_candidate:
                    nombre = nombre_candidate
                    break
                i += 1
            if not nombre:
                return None, None, None

            i += 1
            precios = []
            while i < len(lines):
                posible_precio = lines[i].strip()
                if patron_precio.match(posible_precio):
                    precios.append(posible_precio)
                elif posible_precio and not patron_precio.match(posible_precio):
                    break
                i += 1

            if len(precios) == 0:
                return None, None, None

            precio_normal = precios[0]
            precio_descuento = precios[1] if len(precios) > 1 else None
            return nombre, precio_normal, precio_descuento
        i += 1
    return None, None, None


def extraer_nombre_precios(texto):
    """
    1) Divide en líneas
    2) Aplica Lógica A (número suelto).
       Si falla, Lógica B (categoría "Hombre • ...", etc.)
    """
    lines = texto.splitlines()

    # Lógica A
    nombre, precio_normal, precio_descuento = parse_by_numeric_marker(lines)
    if nombre and precio_normal:
        return nombre, precio_normal, precio_descuento

    # Lógica B
    nombre, precio_normal, precio_descuento = parse_by_category_marker(lines)
    if nombre and precio_normal:
        return nombre, precio_normal, precio_descuento

    # Falló todo
    return None, None, None


# ----------------------------------------------------------------
# 5) Guardar en Excel
# ----------------------------------------------------------------
def guardar_excel_adidas(datos):
    """
    datos: lista de [codigo, nombre, precio_normal, precio_descuento, url_final]
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
# 6) Interfaz Flet
# ----------------------------------------------------------------
def main(page: flet.Page):
    page.title = "Scraping Adidas - Nombre y Precios (con Flet)"

    stop_event = threading.Event()
    is_running = False
    start_time = [0]

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

        for i, sku in enumerate(codigos_list, start=1):
            if stop_event.is_set():
                actualizar_log("Scraping detenido por el usuario.")
                break

            actualizar_log(f"\nProcesando código {i}/{total}: {sku}")
            # 1) Extraer texto con Selenium
            try:
                url_final, texto_copiado = scrape_like_human(sku)
            except Exception as e:
                logging.error(f"Error en scrape_like_human({sku}): {e}")
                actualizar_log(f"ERROR en Selenium: {e}")
                url_final = None
                texto_copiado = ""

            # 2) extraer nombre, precio normal y precio desc.
            nombre_prod, p_normal, p_desc = extraer_nombre_precios(texto_copiado)
            actualizar_log(f" -> Nombre: {nombre_prod}")
            actualizar_log(f" -> Precio Normal: {p_normal}")
            actualizar_log(f" -> Precio Descuento: {p_desc}")

            # Si nada se encontró, pon algo
            if not nombre_prod: nombre_prod = "No detectado"
            if not p_normal: p_normal = "No detectado"
            if not p_desc: p_desc = "N/A"
            if not url_final: url_final = "N/A"

            resultados.append([sku, nombre_prod, p_normal, p_desc, url_final])

            # Actualizar progreso
            progreso = float(i) / float(total)
            progress_bar.value = progreso
            progress_label.value = f"Progreso: {int(progreso * 100)}%"
            page.update()

        # 3) Guardar en Excel
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
                    page.snack_bar = SnackBar(Text(f"Error al leer el archivo: {ex}"), open=True)
            else:
                page.snack_bar = SnackBar(Text("Archivo no válido."), open=True)
            page.update()

    file_picker = FilePicker(on_result=on_file_picked)

    page.add(
        file_picker,
        Column(
            controls=[
                Text("Scraping Adidas - Nombre y Precios", size=18, weight="bold"),
                Text("1) Ingresa SKUs o carga un archivo con SKUs (uno por línea)."),
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
                Text("Log del proceso:", size=14, weight="bold"),
                log_text
            ],
            scroll="auto",
            expand=True
        )
    )


# ----------------------------------------------------------------
# 7) Ejecutar la app Flet
# ----------------------------------------------------------------
if __name__ == "__main__":
    # flet.app(target=main, view=flet.FLET_APP)
    # O si prefieres abrir en el navegador:
    flet.app(target=main, view=flet.WEB_BROWSER)
