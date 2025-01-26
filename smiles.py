from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import os
import time
from telegram.ext import CommandHandler, Updater

# Cargar variables de entorno
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_YEAR = int(os.getenv("DEFAULT_YEAR", "2025"))
SELENIUM_TIMEOUT = 30  # Tiempo de espera en segundos para cargar la página
RESPUESTA = 'No hubo respuesta.'
LOCK_FILE = "process.lock"

# Función para manejar el bloqueo
def is_locked():
    return os.path.exists(LOCK_FILE)

def lock():
    with open(LOCK_FILE, "w") as file:
        file.write("locked")

def unlock():
    if is_locked():
        os.remove(LOCK_FILE)

# Conversión de fecha a timestamp
def date_to_timestamp(year_month: str) -> int:
    """Convierte una fecha en formato YYYY-MM a un timestamp UNIX."""
    year, month = map(int, year_month.split("-"))
    date = datetime(year, month, 1)  # Primer día del mes
    return int(time.mktime(date.timetuple()) * 1000)  # Convertir a milisegundos

def format_table_markdown(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    markdown_text = ""

    if not table:
        return markdown_text

    # Obtener todas las filas
    rows = table.find_all('tr')
    
    # Extraer nombres de aerolíneas de la primera fila (ignorar la celda con 'table-nav')
    airline_names = []
    header_cells = rows[0].find_all(['th', 'td'])
    for td in header_cells:
        td_class = td.get("class", [])
        if "table-nav" in td_class:
            continue
        span = td.find('span')
        if span:
            airline_names.append(span.get_text(strip=True))

    # Recorrer el resto de filas
    for row in rows[1:]:
        row_cells = row.find_all(['th', 'td'])
        
        # El primer cell corresponde al tipo de vuelo (Directo, 1 Escala, etc.)
        flight_type = row_cells[0].get_text(strip=True)
        
        # Omitir la primera celda en prices, pues ya la hemos guardado en flight_type
        # y omitir cualquier celda con la clase 'table-nav'
        price_cells = []
        for cell in row_cells[1:]:
            if "table-nav" not in cell.get("class", []):
                price_cells.append(cell)

        # Convertir en texto
        price_texts = [cell.get_text(strip=True) for cell in price_cells]

        # Combinar aerolíneas y precios (si la primera fila tenía 4 aerolíneas, esperamos 4 prices)
        # Si hay menos celdas que aerolíneas o viceversa, zip limitará a la menor longitud.
        pairs = list(zip(airline_names, price_texts))

        # Construir líneas para la fila actual, omitiendo las vacías.
        row_lines = []
        for airline, price in pairs:
            if price:  # si no está vacío
                row_lines.append(f" ▪️ {airline}: ${price}")

        # Solo agregar la sección si hay al menos un precio para esa fila
        if row_lines:
            markdown_text += f"{flight_type}\n"
            for line in row_lines:
                markdown_text += line + "\n"
            markdown_text += "\n"

    return markdown_text.strip()



# Generar URL
def generate_url(origin: str, destination: str, year_month: str) -> str:
    """Genera la URL para la búsqueda en Smiles."""
    departure_timestamp = date_to_timestamp(year_month)
    url = (
        f"https://www.smiles.com.ar/emission?"
        f"originAirportCode={origin}&destinationAirportCode={destination}"
        f"&departureDate={departure_timestamp}&adults=1&children=0&infants=0"
        f"&isFlexibleDateChecked=false&tripType=1&cabinType=all&currencyCode=ARS"
    )
    return url

# Configurar Selenium
def setup_driver():
    options = Options()
    options.add_argument('--headless')  # Ejecutar en modo headless
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')  # Deshabilitar GPU
    options.add_argument('--window-size=853x1280')  # Establecer tamaño de ventana
    options.add_argument('--start-maximized')  # Iniciar maximizado
    options.add_argument('--disable-extensions')  # Deshabilitar extensiones
    options.add_argument('--disable-infobars')  # Deshabilitar infobars
    options.add_argument('--incognito')  # Modo incógnito
    options.add_argument('--disable-popup-blocking')  # Deshabilitar bloqueo de pop-ups
    options.add_argument('--disable-notifications')  # Deshabilitar notificaciones
    options.add_argument('--disable-blink-features=AutomationControlled')  # Deshabilitar la detección de automatización
    options.add_argument('--remote-debugging-port=9222')  # Habilitar depuración remota
    options.add_argument('--ignore-certificate-errors')  # Ignorar errores de certificado
    options.add_argument('--disable-logging')  # Deshabilitar el registro
    options.add_argument('--log-level=3')  # Establecer nivel de registro
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')  # Establecer agente de usuario

    driver = webdriver.Chrome(options=options)
    return driver

def wait_for_page_load_dos(driver, url):
    """Navega a la URL y espera a que la página termine de cargar."""
    driver.get(url)
    try:
        # Esperar 15 segundos antes de interactuar con la página
        time.sleep(15)

        # Verificar si el elemento existe y hacer clic
        try:
            element = driver.find_element(By.CLASS_NAME, "table-nav.purple-nav")
            element.click()
            print("Se hizo clic en el elemento 'table-nav purple-nav'")
        except:
            print("El elemento 'table-nav purple-nav' no se encontró, no se hizo clic")

        # Esperar un momento para que la acción tenga efecto
        time.sleep(5)

        # Extraer el contenido de la página
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Buscar el único div con class="resume-filters"
        div_resume_filters = soup.find("div", class_="resume-filters")

        # Extraer la tabla dentro de ese div
        if div_resume_filters:
            tabla = div_resume_filters.find("table")
            if tabla:
                return tabla.prettify()
            else:
                print("No se encontró ninguna tabla dentro del div con class='resume-filters'")
                return "No se encontró ninguna tabla dentro del div con class='resume-filters'"
        else:
            print("No se encontró el div con class='resume-filters'")
            return "No se encontró el div con class='resume-filters'"
    except TimeoutException as e:
        return f"Error cargando la página con Selenium: {e}"

# Verificar carga dinámica de la página
def wait_for_page_load(driver, url):
    """Navega a la URL y espera a que la página termine de cargar."""
    driver.get(url)
    try:
        # Esperar 15 segundos antes de interactuar con la página
        time.sleep(15)

        # Buscamos un elemento que esté presente en la página
        WebDriverWait(driver, SELENIUM_TIMEOUT).until(
            EC.presence_of_element_located((By.CLASS_NAME, "resume-filters"))
        )
        
        # Extraer el contenido de la página
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Buscar el único div con class="resume-filters"
        div_resume_filters = soup.find("div", class_="resume-filters")

        # Extraer la tabla dentro de ese div
        if div_resume_filters:
            tabla = div_resume_filters.find("table")
            if tabla:
                return tabla.prettify()
            else:
                print("No se encontró ninguna tabla dentro del div con class='resume-filters'")
                return "No se encontró ninguna tabla dentro del div con class='resume-filters'"
        else:
            print("No se encontró el div con class='resume-filters'")
            return "No se encontró el div con class='resume-filters'"
    except TimeoutException as e:
        return f"Error cargando la página con Selenium: {e}"

# Procesar mensajes
def handle_message(update: Update, context: CallbackContext) -> None:
    if is_locked():
        update.message.reply_text("⚠️ Otro proceso está en ejecución. Por favor, inténtalo más tarde.")
        return

    lock()
    try:
        # Leer mensaje
        message = update.message.text
        parts = message.split()  # Separar por espacios
        if len(parts) != 3:
            update.message.reply_text(
                "❌ Uso incorrecto. \n\n✈️ Debe tener 3 partes: origen (Ezeiza: EZE), destino (Madrid: MAD) y fecha (Formato YYYY-MM). \n\n👉 EZE MAD 2025-12"
            )
            return

        origin, destination, date = parts
        # Si es un alias como "12", convertir a "2024-MM"
        if date.isdigit():
            date = f"{DEFAULT_YEAR}-{date.zfill(2)}"

        # Generar URL
        url = generate_url(origin, destination, date)
        update.message.reply_text(
            f"✅ Nueva petición cargada:\n\n✈️ Origen: {origin}\n✈️ Destino: {destination}\n✈️ Fecha: {date}\n\n🌐 URL: {url}\n\n⌛ Obteniendo resultados..."
        )

        # Usar Selenium INICIO
        driver = setup_driver()
        page_content = wait_for_page_load(driver, url)
        driver.quit()
        # html_file_path = "1.html"
        # with open(html_file_path, "w", encoding="utf-8") as file:
        #     file.write(page_content)

        # # Adjuntar el archivo HTML en el mensaje de respuesta
        # with open(html_file_path, "rb") as file:
        #     update.message.reply_document(document=file, filename="1.html")

        update.message.reply_text(format_table_markdown(page_content))
        # Usar Selenium FIN

        # Usar Selenium INICIO
        driver = setup_driver()
        page_content = wait_for_page_load_dos(driver, url)
        driver.quit()
        # html_file_path = "2.html"
        # with open(html_file_path, "w", encoding="utf-8") as file:
        #     file.write(page_content)

        # # Adjuntar el archivo HTML en el mensaje de respuesta
        # with open(html_file_path, "rb") as file:
        #     update.message.reply_document(document=file, filename="2.html")

        update.message.reply_text(format_table_markdown(page_content))
        # Usar Selenium FIN

    except Exception as e:
        update.message.reply_text(f"Error procesando el mensaje: {e}")
    finally:
        unlock()

# Configurar el bot
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Agregar manejadores
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Iniciar bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
