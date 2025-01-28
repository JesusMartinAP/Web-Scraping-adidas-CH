import time
import logging
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
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def close_cookie_banner(driver):
    """Cierra el banner de cookies si aparece."""
    try:
        cookie_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.gl-cta--primary'))
        )
        cookie_btn.click()
        logging.info("Banner de cookies cerrado.")
    except:
        logging.info("No se pudo cerrar banner (o no existía).")


def close_popup(driver):
    """Cierra el popup inicial si aparece."""
    try:
        pop_close_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.gl-modal__close"))
        )
        pop_close_btn.click()
        logging.info("Pop-up cerrado.")
    except:
        logging.info("No se encontró pop-up (o no se pudo cerrar).")


def copy_page_text_like_human(driver):
    """
    Simula clic en <body>, presiona CTRL+A y CTRL+C para copiar todo el texto.
    Luego lo leemos desde el portapapeles con pyperclip.
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


def scrape_like_human(codigo):
    """
    1) Entra a adidas.cl
    2) Cierra banners/popup
    3) Busca 'codigo' en el buscador
    4) Si hay página de resultados, hace clic en el primer producto
       (si no encuentra resultados, asume que ya estás en la página del producto).
    5) Simula Ctrl+A y Ctrl+C -> retorna todo el texto copiado.
    """
    chrome_options = Options()
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.maximize_window()

    product_text = ""
    final_url = ""

    try:
        # 1) Ir a adidas.cl
        driver.get("https://www.adidas.cl/")
        logging.info("Entrando a Adidas.cl")
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)

        # 2) Cerrar banner de cookies y pop-up
        close_cookie_banner(driver)
        close_popup(driver)

        # 3) Buscar el código
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

        # 4) Ver si hay lista de resultados
        links = driver.find_elements(By.CSS_SELECTOR, 'a[data-auto-id="search-product"]')
        if len(links) > 0:
            logging.info("Hay lista de resultados, clic en el primero.")
            first_link = links[0]
            final_url = first_link.get_attribute("href")
            first_link.click()
            time.sleep(2)

            # A veces abre en la misma pestaña, a veces en otra
            handles = driver.window_handles
            logging.info(f"Ventanas actuales: {handles}")
            driver.switch_to.window(handles[-1])
            time.sleep(2)
        else:
            logging.info("No hay lista de resultados: asumiendo que ya estás en la página del producto.")
            final_url = driver.current_url

        # Esperar que la página cargue
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)

        # 5) Simulamos Ctrl + A, Ctrl + C
        product_text = copy_page_text_like_human(driver)
        logging.info(f"Longitud del texto copiado: {len(product_text)}")

        final_url = driver.current_url

    except Exception as e:
        logging.error(f"Error al procesar el código {codigo}: {e}")

    finally:
        driver.quit()

    return final_url, product_text


# ----------------------------------------------------------------
# Lógica A: buscar "línea solo con dígitos"
# ----------------------------------------------------------------
def parse_by_numeric_marker(lines):
    """
    1) Busca la primera línea con solo dígitos (e.g. "27" o "1").
    2) La siguiente línea no vacía => nombre
    3) Las siguientes líneas que empiecen con '$' => precio_normal, precio_descuento (opcional)
    Devuelve (nombre, precio_normal, precio_descuento) o (None, None, None) si falla.
    """
    patron_digitos = re.compile(r'^\d+$')
    patron_precio = re.compile(r'^\$\d[\d\.,]*')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if patron_digitos.match(line):  # Ej: "27"
            # Buscar nombre
            i += 1
            nombre = None
            while i < len(lines):
                nombre_candidate = lines[i].strip()
                if nombre_candidate:
                    nombre = nombre_candidate
                    break
                i += 1

            if nombre is None:
                return None, None, None

            # Buscar los precios
            i += 1
            precios = []
            while i < len(lines):
                posible_precio = lines[i].strip()
                # si es precio, lo agregamos
                if patron_precio.match(posible_precio):
                    precios.append(posible_precio)
                # si aparece una línea no vacía que no es precio, frenamos
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


# ----------------------------------------------------------------
# Lógica B: buscar "Hombre •", "Mujer •", "Niños •", "Unisex •"
# ----------------------------------------------------------------
def parse_by_category_marker(lines):
    """
    1) Busca la primera línea que coincida con algo como:
       - Hombre • ...
       - Mujer • ...
       - Niños • ...
       - Unisex • ...
    2) La siguiente línea no vacía => nombre
    3) Las siguientes líneas que empiecen con '$' => precio_normal, precio_descuento (opcional)
    Devuelve (nombre, precio_normal, precio_descuento) o (None, None, None) si falla.
    """
    # Regex que detecta "Hombre • Fútbol", "Mujer • Running", "Niños • Fútbol", etc.
    patron_categoria = re.compile(r'^(hombre|mujer|niñ[oa]s|unisex)\s*•', re.IGNORECASE)
    patron_precio = re.compile(r'^\$\d[\d\.,]*')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if patron_categoria.search(line):
            # Buscar nombre
            i += 1
            nombre = None
            while i < len(lines):
                nombre_candidate = lines[i].strip()
                if nombre_candidate:
                    nombre = nombre_candidate
                    break
                i += 1

            if nombre is None:
                return None, None, None

            # Buscar precios
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
    Aplica primero la LÓGICA A (marcador numérico).
    Si no funciona (no encuentra nada), aplica la LÓGICA B (categoría Hombre/Mujer/Niños/Unisex).

    Retorna (nombre, precio_normal, precio_descuento).
    Si ambas lógicas fallan, todo es None.
    """
    lines = texto.splitlines()

    # 1) Intentar LÓGICA A (número suelto)
    nombre, precio_normal, precio_descuento = parse_by_numeric_marker(lines)
    if nombre and precio_normal:
        return nombre, precio_normal, precio_descuento

    # 2) Si falló, probar LÓGICA B (Hombre • Fútbol, etc.)
    nombre, precio_normal, precio_descuento = parse_by_category_marker(lines)
    if nombre and precio_normal:
        return nombre, precio_normal, precio_descuento

    # 3) Si también falló, nada
    return None, None, None


if __name__ == "__main__":
    # =======================
    # 1) OBTENER TEXTO
    # =======================
    # Ejemplo: un SKU que no tenga línea de "digits"
    # (Cambia "IDXXXX" por el SKU real que quieras probar)
    sku_test = "IE2375"
    url, texto_copiado = scrape_like_human(sku_test)

    logging.info(f"URL final: {url}")
    logging.info(f"Texto copiado (longitud): {len(texto_copiado)}")

    # =======================
    # 2) EXTRAER NOMBRE Y PRECIOS
    # =======================
    nombre_producto, precio_normal, precio_descuento = extraer_nombre_precios(texto_copiado)

    print("\n=== RESULTADO PRINCIPAL ===")
    if nombre_producto and precio_normal:
        print(f"Nombre del producto: {nombre_producto}")
        print(f"Precio normal: {precio_normal}")
        if precio_descuento:
            print(f"Precio con descuento: {precio_descuento}")
        else:
            print("No hay precio de oferta (no está en promoción).")
    else:
        print("No se encontró el producto (nombre/precio) con ninguna de las dos lógicas.")
