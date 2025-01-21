import tkinter as tk
from tkinter import messagebox
import time
import os
from datetime import datetime
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

# =========================================================================
# CONFIGURACIONES
# =========================================================================

URL_ADIDAS = "https://www.adidas.cl/"
CSS_SEARCH_INPUT = 'input[data-auto-id="searchinput-desktop"]'
CSS_RESULT_CONTAINER = "div.gl-product-card-container"
CSS_PRICE = "div.gl-price-item.notranslate"

def guardar_excel_adidas(datos):
    """
    Guarda en un archivo Excel la lista de datos [codigo, nombre, precio, url].
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
       - Si no encuentra producto o falla, se registra como "No se encontró".
    2) Retorna la lista con [codigo, nombre, precio, url]
    """

    # Configurar opciones de Chrome
    chrome_options = Options()
    
    # Opción para excluir logs de Chrome
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    
    # Opcional: desactivar GPU (a veces evita algunos errores de renderizado)
    chrome_options.add_argument("--disable-gpu")
    
    # Opcional: modo headless (si no necesitas ver la ventana)
    # chrome_options.add_argument("--headless=new")

    # Crear el servicio usando webdriver_manager (descarga o actualiza el driver)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    resultados = []

    try:
        for codigo in codigos_productos:
            print(f"\n=== Procesando código: {codigo} ===")
            driver.get(URL_ADIDAS)
            time.sleep(2)

            try:
                search_input = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_SEARCH_INPUT))
                )
                search_input.clear()
                search_input.send_keys(codigo)
                search_input.send_keys(Keys.ENTER)

                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_RESULT_CONTAINER))
                )

                # Extraer nombre
                try:
                    product_name_element = driver.find_element(
                        By.CSS_SELECTOR, "div.gl-product-card__details-main a span"
                    )
                    product_name = product_name_element.text.strip()
                except:
                    product_name = "No se encontró nombre"

                # Extraer precio
                try:
                    product_price_element = driver.find_element(By.CSS_SELECTOR, CSS_PRICE)
                    product_price = product_price_element.text.strip()
                except:
                    product_price = "No se encontró precio"

                # Extraer URL
                try:
                    product_link_element = product_name_element.find_element(By.XPATH, "./ancestor::a")
                    product_url = product_link_element.get_attribute("href")
                except:
                    product_url = "No se encontró URL"

                resultados.append([codigo, product_name, product_price, product_url])

            except:
                print(f"No se encontró el código {codigo} (sin resultados).")
                resultados.append([codigo, "No se encontró", "No se encontró", "No se encontró"])

    finally:
        driver.quit()

    return resultados

def iniciar_proceso():
    codigos_str = text_codigos.get("1.0", tk.END)
    codigos_productos = codigos_str.split()

    if not codigos_productos:
        messagebox.showwarning("Advertencia", "No se ingresaron códigos.")
        return

    datos = procesar_codigos_adidas(codigos_productos)
    guardar_excel_adidas(datos)
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
