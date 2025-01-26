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
DEFAULT_YEAR = int(os.getenv("DEFAULT_YEAR", "2024"))
SELENIUM_TIMEOUT = 30  # Tiempo de espera en segundos para cargar la página
RESPUESTA = 'No hubo respuesta.'

# Conversión de fecha a timestamp
def date_to_timestamp(year_month: str) -> int:
    """Convierte una fecha en formato YYYY-MM a un timestamp UNIX."""
    year, month = map(int, year_month.split("-"))
    date = datetime(year, month, 1)  # Primer día del mes
    return int(time.mktime(date.timetuple()) * 1000)  # Convertir a milisegundos

# Formatear tabla en Markdown
def format_table_markdown(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    markdown_text = ""

    rows = table.find_all('tr')
    headers = [header.get_text(strip=True) for header in rows[0].find_all(['th', 'td'])]

    for row in rows[1:]:
        cells = row.find_all(['th', 'td'])
        row_data = [cell.get_text(strip=True) for cell in cells]
        
        if any(row_data[1:]):
            markdown_text += f"{row_data[0]}\n"
            for i, cell in enumerate(row_data[1:], start=1):
                if cell:
                    markdown_text += f"- {headers[i]}: ${cell}\n"
            markdown_text += "\n"
        else:
            markdown_text += f"{row_data[0]}: No se han encontrado.\n\n"

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
    options.add_argument('--window-size=1920x1080')  # Establecer tamaño de ventana
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
                print("Contenido de la tabla encontrada:")
                print(tabla.prettify())
                # La tabla la devolvemos como tipo tabla para mensaje de Telegram

                #return tabla.prettify()
                return soup.prettify()
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

        # Usar Selenium para verificar la página
        driver = setup_driver()
        page_content = wait_for_page_load(driver, url)
        driver.quit()

        # Guardar el contenido en un archivo HTML
        html_file_path = "page_content.html"

        with open(html_file_path, "w", encoding="utf-8") as file:
            file.write(page_content)

        # Adjuntar el archivo HTML en el mensaje de respuesta
        with open(html_file_path, "rb") as file:
            update.message.reply_document(document=file, filename="page_content.html")

        # Enviamos la tabla a Telegram
        update.message.reply_text(format_table_markdown(page_content))

    except Exception as e:
        update.message.reply_text(f"Error procesando el mensaje: {e}")

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
