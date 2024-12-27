from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time

# Variables globales
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Reemplaza con tu token de Telegram
DEFAULT_YEAR = 2024  # Año predeterminado para alias como "12"
SELENIUM_TIMEOUT = 30  # Tiempo de espera en segundos para cargar la página
CHROME_DRIVER_PATH = "/path/to/chromedriver"  # Ruta al chromedriver

# Conversión de fecha a timestamp
def date_to_timestamp(year_month: str) -> int:
    """Convierte una fecha en formato YYYY-MM a un timestamp UNIX."""
    year, month = map(int, year_month.split("-"))
    date = datetime(year, month, 1)  # Primer día del mes
    return int(time.mktime(date.timetuple()) * 1000)  # Convertir a milisegundos

# Generar la URL
def generate_url(origin: str, destination: str, year_month: str) -> str:
    """Genera la URL para la búsqueda en Smiles."""
    departure_timestamp = date_to_timestamp(year_month)
    url = (
        f"https://www.smiles.com.ar/emission?"
        f"originAirportCode={origin}&destinationAirportCode={destination}"
        f"&departureDate={departure_timestamp}&adults=1&children=0&infants=0"
        f"&isFlexibleDateChecked=false&tripType=1&cabinType=all&currencyCode=BRL"
    )
    return url

# Configurar Selenium
def setup_driver():
    """Configura Selenium con opciones para simular un navegador real."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(executable_path=CHROME_DRIVER_PATH, options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        },
    )
    return driver

# Verificar carga dinámica de la página
def wait_for_page_load(driver, url):
    """Navega a la URL y espera a que la página termine de cargar."""
    driver.get(url)
    try:
        wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
        wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'flight-card')]"))
        )
        return driver.page_source
    except Exception as e:
        return f"Error esperando la carga: {e}"

# Procesar mensajes
def handle_message(update: Update, context: CallbackContext) -> None:
    try:
        # Leer mensaje
        message = update.message.text
        parts = message.split()  # Separar por espacios
        if len(parts) != 3:
            update.message.reply_text("Formato incorrecto. Ejemplo: EZE MAD 2024-05")
            return

        origin, destination, date = parts
        # Si es un alias como "12", convertir a "2024-MM"
        if date.isdigit():
            date = f"{DEFAULT_YEAR}-{date.zfill(2)}"

        # Generar URL
        url = generate_url(origin, destination, date)
        
        # Usar Selenium para verificar la página
        driver = setup_driver()
        page_content = wait_for_page_load(driver, url)
        driver.quit()

        # Enviar resultados
        update.message.reply_text(f"Resultados obtenidos de {url}")
        if "Error" in page_content:
            update.message.reply_text(page_content)
        else:
            update.message.reply_text("Página cargada correctamente. Procesa el contenido HTML según lo necesario.")
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
