import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import re
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

# ------------------------------------------------------------------
# 1) PARSEAR EL TEXTO (SIMIL "CTRL + A") EN PÁGINA DETALLE
# ------------------------------------------------------------------
def extraer_nombre_precio_desde_texto(full_text):
    """
    Ajusta la lógica según tus patrones reales.
    Ejemplo: buscar "zapatos de fútbol predator pro terreno firme" y línea siguiente con '$'.
    """
    nombre_buscado = "zapatos de fútbol predator pro terreno firme"
    product_name_found = None
    product_price_found = None

    lines = full_text.split('\n')
    for i, line in enumerate(lines):
        if nombre_buscado in line.lower():
            product_name_found = line.strip()
            # Buscamos el precio en líneas siguientes que empiecen con "$"
            for j in range(i+1, len(lines)):
                if lines[j].startswith('$'):
                    product_price_found = lines[j].strip()
                    break
            break

    # Regex fallback para nombre
    if not product_name_found:
        pattern = re.compile(r"(zapatos de fútbol.*?terreno firme)", re.IGNORECASE | re.DOTALL)
        match_name = pattern.search(full_text)
        if match_name:
            product_name_found = match_name.group(1).strip()

    # Regex fallback para precio
    if not product_price_found:
        match_price = re.search(r"\$\d{1,3}(\.\d{3})*(,\d+)?", full_text)
        if match_price:
            product_price_found = match_price.group(0)

    return product_name_found, product_price_found


# ------------------------------------------------------------------
# 2) CERRAR BANNER DE COOKIES
# ------------------------------------------------------------------
def close_cookie_banner(driver):
    """
    Ajusta el selector al botón del banner de cookies real en tu región.
    """
    try:
        cookie_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.gl-cta--primary'))
        )
        cookie_btn.click()
    except TimeoutException:
        pass
    except Exception as e:
        print("Error al cerrar banner de cookies:", e)


# ------------------------------------------------------------------
# 3) CERRAR POP-UP (LA “X”)
# ------------------------------------------------------------------
def close_popup(driver):
    """
    Intenta cerrar el pop-up con la "X".
    Ajusta el selector si tu HTML difiere (por id, clase, etc.).
    """
    try:
        pop_close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.gl-modal__close"))
        )
        pop_close_btn.click()
    except TimeoutException:
        pass
    except Exception as e:
        print("Error al cerrar pop-up:", e)


# ------------------------------------------------------------------
# 4) FLUJO PRINCIPAL DE SCRAPING: ABRIR, CERRAR BANNERS, CLIQUEAR ÍCONO BUSCAR, ETC.
# ------------------------------------------------------------------
def scrape_code_in_adidas(codigo):
    """
    - Abre adidas.cl
    - Cierra banner de cookies y pop-up
    - Haz clic en el ícono de búsqueda (span -> svg -> #search)
    - Pega el código en el campo de búsqueda y Enter
    - Abre primer producto
    - Obtiene body.text, parsea nombre y precio
    - Retorna (nombre, precio, url_final)
    """

    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    product_name_found = None
    product_price_found = None
    final_url = None

    try:
        # 1) Ir a adidas.cl
        driver.get("https://www.adidas.cl/")
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(2)

        # 2) Cerrar banner de cookies y pop-up
        close_cookie_banner(driver)
        close_popup(driver)

        # 3) Hacer clic en el ícono de BÚSQUEDA
        #    Ej: si tu HTML es: <span class="gl-icon__wrapper" role="img"><svg ...><use xlink:href="#search"></use></svg></span>
        #    Lo más práctico es cliquear el padre <button> si existe. Si no, busca el <span>.
        try:
            search_icon = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span.gl-icon__wrapper[role='img'] svg.gl-icon use[xlink\\:href='#search']"))
            )
            # Selenium no puede hacer click en <use>. Haz click en su elemento padre
            #   busquemos .find_element(By.XPATH, "./ancestor::button") o un contenedor <span>.
            search_icon_parent = search_icon.find_element(By.XPATH, "./ancestor::span")
            search_icon_parent.click()
        except TimeoutException:
            # Si no encuentra el ícono, quizas la barra de búsqueda ya esté visible
            pass

        # 4) Buscar el campo de búsqueda
        #    (Puede que aparezca tras pulsar el ícono; ajusta si no lo encuentra)
        search_input = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[data-auto-id="searchinput-desktop"]'))
        )
        search_input.clear()
        search_input.send_keys(codigo)
        search_input.send_keys(Keys.ENTER)

        # 5) Esperar resultados
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.gl-product-card"))
        )

        # Tomar primer producto
        first_product_link = driver.find_element(By.CSS_SELECTOR, "div.gl-product-card__details-main a")
        final_url = first_product_link.get_attribute("href")
        first_product_link.click()

        # 6) Capturar texto en la página de detalle
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(2)
        full_text = driver.find_element(By.TAG_NAME, 'body').text

        product_name_found, product_price_found = extraer_nombre_precio_desde_texto(full_text)
        final_url = driver.current_url

    except Exception as e:
        print(f"Error procesando código {codigo}: {e}")
    finally:
        driver.quit()

    return product_name_found, product_price_found, final_url


# ------------------------------------------------------------------
# 5) GUARDAR EXCEL
# ------------------------------------------------------------------
def guardar_excel_adidas(datos):
    df = pd.DataFrame(datos, columns=["Código", "Nombre", "Precio", "URL final"])
    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre_archivo = f"Adidas_Scraping_{fecha_hora}.xlsx"
    df.to_excel(nombre_archivo, index=False)
    print(f"Datos guardados en: {nombre_archivo}")


# ------------------------------------------------------------------
# 6) TKINTER APP: PROGRESO, CRONÓMETRO, STOP
# ------------------------------------------------------------------
class AdidasScraperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Web Scraping Adidas - Clic en icono de búsqueda")
        self.geometry("600x350")

        style = ttk.Style(self)
        style.theme_use("clam")

        self.stop_event = threading.Event()
        self.is_running = False
        self.start_time = None

        self.create_widgets()
        self.update_timer()

    def create_widgets(self):
        lbl_instruccion = ttk.Label(self, text="Ingresa CÓDIGOS de producto (uno por línea):")
        lbl_instruccion.pack(padx=10, pady=5, anchor="w")

        self.text_codigos = tk.Text(self, width=70, height=6)
        self.text_codigos.pack(padx=10, pady=5)

        frame_botones = ttk.Frame(self)
        frame_botones.pack(pady=5)

        btn_iniciar = ttk.Button(frame_botones, text="Iniciar", command=self.iniciar_proceso)
        btn_iniciar.pack(side="left", padx=10)

        btn_detener = ttk.Button(frame_botones, text="Detener", command=self.detener_proceso)
        btn_detener.pack(side="left", padx=10)

        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", length=400,
                                            mode="determinate", variable=self.progress_var)
        self.progress_bar.pack(pady=5)

        self.label_progress_var = tk.StringVar(value="Esperando...")
        self.label_progress = ttk.Label(self, textvariable=self.label_progress_var)
        self.label_progress.pack()

        self.timer_var = tk.StringVar(value="Tiempo transcurrido: 00:00")
        self.label_timer = ttk.Label(self, textvariable=self.timer_var, font=("Helvetica", 10, "bold"))
        self.label_timer.pack(pady=5)

    def iniciar_proceso(self):
        if self.is_running:
            messagebox.showwarning("Advertencia", "Ya hay un proceso en ejecución.")
            return

        self.stop_event.clear()
        self.is_running = True
        self.start_time = time.time()

        codigos_str = self.text_codigos.get("1.0", tk.END).strip()
        self.codigos_list = codigos_str.split()
        if not self.codigos_list:
            messagebox.showwarning("Advertencia", "No se ingresaron códigos.")
            self.is_running = False
            return

        self.label_progress_var.set("Iniciando scraping...")
        self.progress_var.set(0)

        hilo = threading.Thread(target=self.run_scraping, daemon=True)
        hilo.start()

    def run_scraping(self):
        resultados = []
        total = len(self.codigos_list)

        for i, codigo in enumerate(self.codigos_list, start=1):
            if self.stop_event.is_set():
                break

            progress = int(i / total * 100)
            self.progress_var.set(progress)
            self.label_progress_var.set(f"Procesando {i} de {total}")
            self.update_idletasks()

            nombre, precio, url_final = scrape_code_in_adidas(codigo)

            if not nombre:
                nombre = "No se encontró"
            if not precio:
                precio = "No se encontró"
            if not url_final:
                url_final = "No se obtuvo URL"

            resultados.append([codigo, nombre, precio, url_final])

        if resultados:
            guardar_excel_adidas(resultados)

        self.is_running = False
        if self.stop_event.is_set():
            self.label_progress_var.set("Proceso detenido")
        else:
            self.label_progress_var.set("Proceso finalizado")

        messagebox.showinfo("Información", "Scraping finalizado (o detenido).")

    def detener_proceso(self):
        if not self.is_running:
            messagebox.showwarning("Advertencia", "No hay proceso en ejecución.")
            return
        self.stop_event.set()

    def update_timer(self):
        if self.is_running and self.start_time is not None:
            elapsed = int(time.time() - self.start_time)
            minutes, seconds = divmod(elapsed, 60)
            self.timer_var.set(f"Tiempo transcurrido: {minutes:02d}:{seconds:02d}")
        self.after(1000, self.update_timer)


# ------------------------------------------------------------------
# 7) EJECUTAR LA APP
# ------------------------------------------------------------------
if __name__ == "__main__":
    app = AdidasScraperApp()
    app.mainloop()
