import tkinter as tk
from tkinter import messagebox
import time
import os
from datetime import datetime
import pandas as pd

# ==== SELENIUM IMPORTS (Versión 4) ====
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================================================================
# CONFIGURACIONES Y SELECTORES
# =========================================================================

# URL de Adidas Chile
URL_ADIDAS = "https://www.adidas.cl/"

# Selector del campo de búsqueda
CSS_SEARCH_INPUT = 'input[data-auto-id="searchinput-desktop"]'

# Selector de contenedor de resultados (para esperar a que aparezcan)
CSS_RESULT_CONTAINER = "div.gl-product-card-container"

# Selector para obtener el precio (clase genérica que usa Adidas)
CSS_PRICE = "div.gl-price-item.notranslate"

# =========================================================================
# FUNCIONES PRINCIPALES
# =========================================================================

def guardar_excel_adidas(datos):
    """
    Guarda en un archivo Excel la lista de datos [codigo, nombre, precio, url].
    Requiere 'openpyxl' (pip install openpyxl).
    """
    df = pd.DataFrame(datos, columns=["Código", "Nombre", "Precio", "URL"])
    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre_archivo = f"Adidas_Scraping_{fecha_hora}.xlsx"
    ruta_archivo = os.path.join(os.getcwd(), nombre_archivo)
    df.to_excel(ruta_archivo, index=False)
    print(f"Datos guardados en: {ruta_archivo}")

def procesar_codigos_adidas(codigos_productos):
    """
    1) Para cada código en 'codigos_productos':
       - Entra a https://www.adidas.cl
       - Busca el código en la barra de búsqueda
       - Extrae nombre, precio y URL del primer resultado
       - Si no encuentra producto, lo registra como 'No se encontró'
    2) Retorna la lista con [codigo, nombre, precio, url]
    """

    # Ajusta la ruta a tu ChromeDriver local
    driver_path = "chromedriver"

    # Crear el objeto Service para Selenium 4
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)

    # Lista donde guardaremos los resultados
    resultados = []

    try:
        for codigo in codigos_productos:
            print(f"\n=== Procesando código: {codigo} ===")
            # Ir a la página principal de Adidas Chile
            driver.get(URL_ADIDAS)
            time.sleep(2)  # Espera breve para asegurar carga de la página

            try:
                # Localizar el campo de búsqueda
                search_input = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_SEARCH_INPUT))
                )
                search_input.clear()
                search_input.send_keys(codigo)
                search_input.send_keys(Keys.ENTER)

                # Esperar a que aparezcan resultados o el contenedor de productos
                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_RESULT_CONTAINER))
                )

                # Intentar extraer nombre del primer producto
                # Podrías buscar un selector más genérico, p.e. primer <span> dentro de una tarjeta.
                try:
                    # Un approach genérico: tomar el primer .gl-product-card__details-main a span
                    product_name_element = driver.find_element(
                        By.CSS_SELECTOR,
                        "div.gl-product-card__details-main a span"
                    )
                    product_name = product_name_element.text.strip()
                except:
                    product_name = "No se encontró nombre"

                # Extraer precio (genérico: "div.gl-price-item.notranslate")
                try:
                    product_price_element = driver.find_element(By.CSS_SELECTOR, CSS_PRICE)
                    product_price = product_price_element.text.strip()
                except:
                    product_price = "No se encontró precio"

                # Extraer la URL del producto (buscamos ancestro <a> del nombre o el primer link)
                try:
                    product_link_element = product_name_element.find_element(By.XPATH, "./ancestor::a")
                    product_url = product_link_element.get_attribute("href")
                except:
                    product_url = "No se encontró URL"

                # Guardamos en la lista
                resultados.append([codigo, product_name, product_price, product_url])

            except Exception as e:
                print(f"Error al procesar {codigo}: {e}")
                resultados.append([codigo, "No se encontró", "No se encontró", "No se encontró"])

    finally:
        # Cerrar el navegador
        driver.quit()

    return resultados

def iniciar_proceso():
    """
    Función que se llama al presionar el botón en Tkinter:
    1) Toma el texto (códigos) ingresados en el cuadro.
    2) Llama a procesar_codigos_adidas.
    3) Guarda resultados en Excel.
    4) Muestra un messagebox final.
    """
    codigos_str = text_codigos.get("1.0", tk.END)
    # Convertir a lista (separando por espacios o saltos de línea)
    codigos_productos = codigos_str.split()

    if not codigos_productos:
        messagebox.showwarning("Advertencia", "No se ingresaron códigos.")
        return

    # Llamamos la función principal de scraping
    datos = procesar_codigos_adidas(codigos_productos)

    # Guardamos en Excel
    guardar_excel_adidas(datos)

    # Mostramos notificación final
    messagebox.showinfo("Proceso finalizado", "¡El proceso de scraping ha concluido exitosamente!")

# =========================================================================
# INTERFAZ TKINTER
# =========================================================================

ventana = tk.Tk()
ventana.title("Web Scraping Adidas Chile")

lbl_instruccion = tk.Label(ventana, text="Pega aquí los códigos (separados por espacios o líneas):")
lbl_instruccion.pack(padx=10, pady=5)

text_codigos = tk.Text(ventana, width=60, height=10)
text_codigos.pack(padx=10, pady=5)

btn_iniciar = tk.Button(ventana, text="Iniciar proceso", command=iniciar_proceso, bg="lightblue")
btn_iniciar.pack(pady=10)

ventana.mainloop()
