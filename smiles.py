from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import os
import time
import html
import shutil
import glob


# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_YEAR = int(os.getenv("DEFAULT_YEAR", "2025"))
SELENIUM_TIMEOUT = 15  # Timeout in seconds for page loading
RESPUESTA = 'No hubo respuesta.'
LOCK_FILE = "process.lock"

def is_locked():
    """
    Check if another process is running by looking for the lock file.
    """
    return os.path.exists(LOCK_FILE)

def lock():
    """Create a lock file to indicate that a process is running."""
    with open(LOCK_FILE, "w") as file:
        file.write("locked")

def unlock():
    """Remove the lock file if it exists to end the process indication."""
    if is_locked():
        os.remove(LOCK_FILE)

def date_to_timestamp(year_month_day: str) -> int:
    """
    Convert date in 'YYYY-MM-DD' format to UNIX timestamp in milliseconds.
    """
    year, month, day = map(int, year_month_day.split("-"))
    date = datetime(year, month, day)
    return int(time.mktime(date.timetuple()) * 1000)

def generate_url(origin: str, destination: str, year_month_day: str) -> str:
    """
    Generate URL for Smiles flight search.
    """
    departure_timestamp = date_to_timestamp(year_month_day)
    return (
        f"https://www.smiles.com.ar/emission?"
        f"originAirportCode={origin}&destinationAirportCode={destination}"
        f"&departureDate={departure_timestamp}&adults=1&children=0&infants=0"
        f"&isFlexibleDateChecked=false&tripType=1&cabinType=all&currencyCode=ARS"
    )

def setup_driver():
    """
    Set up and configure Selenium WebDriver with Chrome options for headless browsing.
    """
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--incognito')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-logging')
    options.add_argument('--log-level=3')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')
    
    return webdriver.Chrome(options=options)

def clean_temp_folders():
    """
    Elimina todas las carpetas temporales creadas por Chromium.
    """
    temp_dir = os.getenv('TEMP', '/tmp')
    temp_folders = glob.glob(os.path.join(temp_dir, '.com.google.Chrome.*'))
    for folder in temp_folders:
        try:
            shutil.rmtree(folder)
        except Exception as e:
            print(f"Error al eliminar la carpeta {folder}: {e}")
    print("Carpetas temporales eliminadas. Sesion empezada o terminada.")

def obtener_listado(driver, url, date):
    """
    Navega a la URL, espera que se cargue el div 'selection-flights'
    y recorre cada div con clase 'group-info-flights' para extraer los datos.
    
    Retorna un mensaje en formato HTML con los detalles de cada vuelo.
    """
    driver.get(url)
    try:
        print("Esperando a que se cargue la página...")

        # Espera a que se cargue el contenedor principal de vuelos
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "selection-flights"))
        )
        
        # Extraer el contenido del div 'selection-flights'
        soup = BeautifulSoup(driver.page_source, "html.parser")
        selection_div = soup.find("div", class_="selection-flights")
        if not selection_div:
            return ["No se encontraron resultados de vuelos."]

        # Lista donde se irán almacenando los datos de cada vuelo
        vuelos = []
        # Itera sobre cada div que agrupa la información de un vuelo
        grupos = selection_div.find_all("div", class_="group-info-flights")
        for grupo in grupos[:5]:  # Limitar a los primeros 5 vuelos
            vuelo = {}

            # Extrae la sección de detalles del viaje
            travel_details = grupo.find("div", class_="travel-details")
            if travel_details:
                origen_div = travel_details.find("div", class_="travel-origin")
                destino_div = travel_details.find("div", class_="travel-arrival")
                info_viaje = travel_details.find("div", class_="travel-info")
                escalas = ""
                duracion = ""
                if info_viaje:
                    escalas_elem = info_viaje.find("div", class_="travel-stops")
                    duracion_elem = info_viaje.find("div", class_="travel-duration")
                    if escalas_elem:
                        escalas = escalas_elem.get_text(" ", strip=True).lower()
                    if duracion_elem:
                        duracion = duracion_elem.get_text(" ", strip=True)
                
                origen_text = origen_div.get_text(" ", strip=True) if origen_div else "N/A"
                destino_text = destino_div.get_text(" ", strip=True) if destino_div else "N/A"
                
                # Asegurarse de que siempre se incluya "hs" y "min"
                origen_text = origen_text.replace("h", " hs ")
                if "min" not in origen_text:
                    origen_text += " min"
                
                destino_text = destino_text.replace("h", " hs ")
                if "min" not in destino_text:
                    destino_text += " min"
                
                vuelo["origen"] = origen_text
                vuelo["destino"] = destino_text
                vuelo["escalas"] = escalas
                vuelo["duracion"] = duracion

            # Extrae la disponibilidad de asientos
            seat_info_div = grupo.find("div", class_="info-seat")
            vuelo["disponibles"] = seat_info_div.get_text(" ", strip=True).replace("!", "").strip() if seat_info_div else "N/A"

            # Extrae los precios
            precios = []
            miles_group = grupo.find("div", class_="miles-group")
            if miles_group:
                precio_items = miles_group.find_all("li", class_="list-group-item")
                for item in precio_items:
                    texto_precio = item.get_text(" ", strip=True)
                    if texto_precio:
                        # Formatear el precio según las reglas especificadas
                        if "Club Smiles" in texto_precio:
                            if "+" in texto_precio:
                                partes = texto_precio.split("+")
                                millas = partes[0].strip() + " millas"
                                dinero = partes[1].split("x")[0].strip()
                                precios.append(f"{millas} + {dinero} x Club Smiles")
                            else:
                                millas = texto_precio.split("x")[0].strip() + " millas"
                                precios.append(f"{millas} x Club Smiles")
                        else:
                            millas = texto_precio.split("x")[0].strip() + " millas"
                            precios.append(f"{millas} x Club Smiles")
            vuelo["precios"] = precios

            vuelos.append(vuelo)

        # Formatea la información en un mensaje HTML
        mensajes = []
        mensaje = ""
        for vuelo in vuelos:
            vuelo_info = (
                "<b>✈️ Vuelo para el " + date + "</b>\n"
                f"📍 • <b>Origen:</b> {html.escape(vuelo.get('origen', 'N/A'))}\n"
                f"📍 • <b>Destino:</b> {html.escape(vuelo.get('destino', 'N/A'))}\n"
                f"⏳ • <b>{html.escape(vuelo.get('duracion', 'N/A'))} horas</b> de duración\n"
                f"🔁 • <b>Escalas:</b> {html.escape(vuelo.get('escalas', 'N/A'))}\n"
                f"💺 • <b>{html.escape(vuelo.get('disponibles', 'N/A'))}</b> \n"
                "💰 • <b>Precios:</b>\n<code>"
            )
            if vuelo.get("precios"):
                for prec in vuelo["precios"]:
                    vuelo_info += f" ▫️ {html.escape(prec)}\n"
            vuelo_info += "</code>\n"

            if len(mensaje) + len(vuelo_info) > 4096:  # Telegram message limit
                mensajes.append(mensaje)
                mensaje = vuelo_info
            else:
                mensaje += vuelo_info

        if mensaje:
            mensajes.append(mensaje)

        return mensajes if mensajes else ["No se encontró información en el listado."]

    except Exception as e:
        return [f"Error al obtener datos: {e}"]
    finally:
        driver.quit()
        clean_temp_folders()

def handle_message(update: Update, context: CallbackContext) -> None:
    if is_locked():
        update.message.reply_text("⚠️ Another process is running. Please try again later.")
        return

    lock() # Lock the process to prevent concurrent requests
    try:
        message = update.message.text.split()
        if len(message) != 3:
            update.message.reply_text(
                "❌ Uso incorrecto. \n\n✈️ Debe tener 3 partes: origen (Buenos Aires: BUE), destino (Madrid: MAD) y la fecha (Formato MM-DD). \n\n👉 Por ejemplo: EZE MAD 12-25\n💡 <a href='https://es.wikipedia.org/wiki/Anexo:Aeropuertos_según_el_código_IATA'>Aprende los códigos de aereopuertos acá</a>",
                parse_mode='HTML'
            )
            return

        origin, destination, date = message
        date = f"{DEFAULT_YEAR}-{date}"

        url = generate_url(origin, destination, date)
        update.message.reply_text("⌛ Esperá! Obteniendo resultados desde la URL: " + url, parse_mode='HTML')

        driver = setup_driver()
        listados = obtener_listado(driver, url, date)

        for listado in listados:
            update.message.reply_text(listado, parse_mode='HTML')

    except Exception as e:
        error_message = html.escape(str(e))
        update.message.reply_text(f"❌ Comunicale el error al administrador: <b>{error_message}</b>", parse_mode='HTML')
    finally:
        unlock()

def main():
    """
    Initialize and run the Telegram bot.
    """
    clean_temp_folders()
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
