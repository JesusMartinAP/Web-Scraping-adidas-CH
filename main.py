import time
import re
import os
from datetime import datetime
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

def extraer_nombre_precio_desde_texto(full_text):
    """
    Busca en el texto completo (body.text) el nombre y el precio.
    Ajusta la lógica según tus patrones reales.
    """

    # Convertimos todo a minúsculas para facilitar la comparación
    lower_text = full_text.lower()

    # ---------------------------
    # 1) EXTRAER NOMBRE
    # ---------------------------
    # Supongamos que quieres encontrar la línea que contenga
    # "zapatos de fútbol predator pro terreno firme".
    # (Si varía el texto, ajusta a tu gusto)
    nombre_buscado = "zapatos de fútbol predator pro terreno firme"

    product_name_found = None
    product_price_found = None

    # 1.A) Recorremos línea por línea
    lines = full_text.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if nombre_buscado in line_lower:
            product_name_found = line.strip()  # Tomamos la línea exacta como "nombre"

            # 2) Buscamos el precio en las líneas posteriores
            #    Suponiendo que el precio empiece con "$"
            for j in range(i+1, len(lines)):
                if lines[j].startswith('$'):
                    product_price_found = lines[j].strip()
                    break
            break

    # 1.B) Si no se encontró nada con esa línea, puedes usar un Regex de fallback
    #      para buscar "Zapatos de fútbol" + "terreno firme" en un rango de texto.
    if not product_name_found:
        # Ejemplo de expresión regular flexible:
        # "zapatos de fútbol" + algo + "terreno firme"
        pattern = re.compile(r"(zapatos de fútbol.*?terreno firme)", re.IGNORECASE | re.DOTALL)
        match_name = pattern.search(full_text)
        if match_name:
            product_name_found = match_name.group(1).strip()

    # ---------------------------
    # 2) EXTRAER PRECIO (si no se encontró arriba)
    # ---------------------------
    if not product_price_found:
        # Ejemplo: buscar la primera coincidencia que se parezca a $###.### (o con puntos).
        match_price = re.search(r"\$\d{1,3}(\.\d{3})*(,\d+)?", full_text)
        if match_price:
            product_price_found = match_price.group(0)

    return product_name_found, product_price_found


def scrape_by_full_text(url):
    """
    1. Carga la URL dada en Chrome.
    2. Obtiene todo el texto visible (body.text).
    3. Extrae el nombre y el precio usando la función de parseo de texto.
    4. Retorna (nombre, precio, url_actual).
    """

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    product_name_found = None
    product_price_found = None
    final_url = None

    try:
        driver.get(url)
        time.sleep(3)  # Espera para que cargue la página

        # 1) Capturar todo el texto del <body>
        full_text = driver.find_element(By.TAG_NAME, 'body').text

        # 2) Extraer nombre y precio
        product_name_found, product_price_found = extraer_nombre_precio_desde_texto(full_text)

        # 3) Obtener la URL actual (simula F6)
        final_url = driver.current_url

    except Exception as e:
        print(f"Error al procesar la URL {url}:\n{e}")
    finally:
        driver.quit()

    return product_name_found, product_price_found, final_url


if __name__ == "__main__":
    # EJEMPLO: Asume que ya estás en una URL donde
    # "Zapatos de Fútbol Predator Pro Terreno Firme" y "$129.990" aparecen en el texto.
    # Ajusta la URL a tu caso real (página de detalle del producto, etc.)
    url_producto = "https://www.adidas.cl/zapatos-de-futbol-x-speedportal.1-terreno-firme/GZ5109.html"  # URL a modo de ejemplo

    nombre, precio, la_url = scrape_by_full_text(url_producto)

    print("===========================================")
    print("Nombre encontrado:", nombre)
    print("Precio encontrado:", precio)
    print("URL actual:", la_url)
    print("===========================================")