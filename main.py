#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de ejemplo para automatizar la búsqueda de productos en adidas.cl
y extraer el nombre, precio y URL del producto utilizando Selenium.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def scrape_adidas_product(code_to_search="ID3856"):
    """
    Abre adidas.cl, ingresa el código del producto en la barra de búsqueda
    y extrae nombre, precio y URL del primer resultado.
    """
    # Ruta del WebDriver (Ajusta la ruta exacta donde tengas tu driver)
    driver_path = "chromedriver"

    # Inicializa el navegador (Chrome)
    # Si utilizas un navegador diferente, modifica el driver correspondiente.
    driver = webdriver.Chrome(executable_path=driver_path)

    # Implicit wait (para que Selenium espere si un elemento no aparece de inmediato)
    driver.implicitly_wait(10)

    try:
        # 1. Ingresar a la página principal de Adidas Chile
        driver.get("https://www.adidas.cl/")

        # Esperamos unos segundos para que se cargue todo
        time.sleep(3)

        # 2. Localizar el campo de búsqueda por su atributo 'data-auto-id'
        search_input = driver.find_element(By.CSS_SELECTOR, 'input[data-auto-id="searchinput-desktop"]')

        # Escribimos el código y presionamos Enter
        search_input.send_keys(code_to_search)
        search_input.send_keys(Keys.ENTER)

        # 3. Esperar a que aparezca el contenedor de resultados o un elemento de la página de resultados
        #    (utilizamos WebDriverWait para esperar hasta que el elemento sea visible)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.gl-product-card-container")))
        
        # En este ejemplo, asumimos que el primer resultado que contenga el nombre "Predator"
        # será el que contenga el producto. Ajusta los selectores según convenga.

        # 4. Extraer el nombre del producto
        #    Ajusta el XPATH o el selector para el producto que te interese.
        #    Aquí se usa un XPATH que busca un span con la palabra 'Predator' en el texto.
        try:
            product_name_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Predator')]")
        except:
            # Si no se encuentra, intenta tomar el primer resultado de forma genérica
            product_name_element = driver.find_element(By.CSS_SELECTOR, "div.gl-product-card__details-main > a span")

        product_name = product_name_element.text

        # 5. Extraer el precio
        #    La clase 'gl-price-item' suele usarse en Adidas para mostrar el precio
        try:
            product_price_element = driver.find_element(By.CSS_SELECTOR, "div.gl-price-item.notranslate")
            product_price = product_price_element.text
        except:
            # Dependiendo de la página, el precio podría tener otro selector
            product_price = "No se pudo extraer el precio"

        # 6. Extraer la URL del producto
        #    Para ello, subimos al elemento ancestro <a> para tomar su 'href'.
        #    Asumiendo que el producto_name_element está dentro de un enlace <a>.
        try:
            product_link_element = product_name_element.find_element(By.XPATH, "./ancestor::a")
            product_url = product_link_element.get_attribute("href")
        except:
            # Si falla, intentamos localizar el <a> contenedor más genérico en la tarjeta del producto
            product_link_element = driver.find_element(By.CSS_SELECTOR, "div.gl-product-card__details-main > a")
            product_url = product_link_element.get_attribute("href")

        # 7. Imprimir la información obtenida
        print("======================================")
        print("Código Buscado:  ", code_to_search)
        print("Nombre Producto: ", product_name)
        print("Precio:          ", product_price)
        print("URL del Producto:", product_url)
        print("======================================")

    except Exception as e:
        print("Ocurrió un error:", e)

    finally:
        # Cerrar el navegador
        driver.quit()


if __name__ == "__main__":
    # Llamar a la función con el código que necesites
    scrape_adidas_product("ID3856")
