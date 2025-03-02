from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import os
import time
import html
import shutil
import glob
import re

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_YEAR = int(os.getenv("DEFAULT_YEAR", "2025"))
SELENIUM_TIMEOUT = 15  # Reducido de 15 a 10 segundos para ser más ágil
RESPUESTA = 'No hubo respuesta.'
LOCK_FILE = "process.lock"

# Variables globales para manejar el navegador
driver = None

def is_locked():
    """Check if another process is running by looking for the lock file."""
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
    """Convert date in 'YYYY-MM-DD' format to UNIX timestamp in milliseconds."""
    year, month, day = map(int, year_month_day.split("-"))
    date = datetime(year, month, day)
    return int(time.mktime(date.timetuple()) * 1000)

def generate_url(origin: str, destination: str, year_month_day: str) -> str:
    """Generate URL for Smiles flight search."""
    departure_timestamp = date_to_timestamp(year_month_day)
    return (
        f"https://www.smiles.com.ar/emission?"
        f"originAirportCode={origin}&destinationAirportCode={destination}"
        f"&departureDate={departure_timestamp}&adults=1&children=0&infants=0"
        f"&isFlexibleDateChecked=false&tripType=1&cabinType=all"
    )

def setup_driver():
    """Set up and configure Selenium WebDriver with optimized Chrome options."""
    options = Options()
    # Configuración mínima y optimizada para velocidad
    options.add_argument('--headless')  # Modo sin interfaz gráfica
    options.add_argument('--no-sandbox')  # Necesario en algunos entornos
    options.add_argument('--disable-dev-shm-usage')  # Evita problemas en entornos con poca memoria
    options.add_argument('--disable-gpu')  # No necesitamos GPU
    options.add_argument('--disable-extensions')  # Desactiva extensiones
    options.add_argument('--disable-blink-features=AutomationControlled')  # Evita detección de bots
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    # Optimizaciones adicionales para reducir carga
    options.add_argument('--disable-images')  # Bloquea imágenes para reducir tiempo de carga
    options.add_argument('--blink-settings=imagesEnabled=false')  # Desactiva imágenes a nivel de Blink
    options.add_argument('--disable-javascript')  # Desactiva JavaScript si no es necesario (evaluar si el sitio lo requiere)

    # Crear el navegador
    return webdriver.Chrome(options=options)

def clean_temp_folders():
    """Elimina todas las carpetas temporales creadas por Chromium."""
    temp_dir = os.getenv('TEMP', '/tmp')
    temp_folders = glob.glob(os.path.join(temp_dir, '.com.google.Chrome.*'))
    for folder in temp_folders:
        try:
            shutil.rmtree(folder)
        except Exception as e:
            print(f"Error al eliminar la carpeta {folder}: {e}")
    print("[DEBUG] Carpetas temporales eliminadas.")

def restart_driver():
    """Restart the Selenium WebDriver."""
    global driver
    if driver is not None:
        driver.quit()
    driver = setup_driver()

def obtener_listado(driver, url, date, retries=3):
    print(f"[DEBUG] Cargando la URL: {url}")
    driver.get(url)
    
    try:
        print("[DEBUG] Esperando a que se cargue el contenedor principal de vuelos...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "selection-flights"))
        )
        print("[DEBUG] Contenedor 'selection-flights' encontrado.")

        print("[DEBUG] Aplicando espera adicional de 5 segundos para carga dinámica...")
        time.sleep(5)

        print("[DEBUG] Extrayendo el contenido de la página con BeautifulSoup...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Guardar el HTML en /tmp/test.html para depuración
        with open("/tmp/test.html", "w", encoding="utf-8") as file:
            file.write(str(soup))
        print("[DEBUG] HTML guardado en /tmp/test.html para depuración.")

        selection_divs = soup.find_all("div", class_="selection-flights")
        selection_div = None
        for div in selection_divs:
            if div.find("div", class_="group-info-flights"):
                selection_div = div
                break

        if not selection_div:
            print("[DEBUG] No se encontró un div 'selection-flights' con contenido.")
            return ["No se encontraron resultados de vuelos."]
        
        print("[DEBUG] Div 'selection-flights' con contenido encontrado. Procesando vuelos...")
        grupos = selection_div.find_all("div", class_="group-info-flights")
        if not grupos:
            print("[DEBUG] No se encontraron elementos 'group-info-flights'.")
            return ["No se encontró información en el listado."]

        vuelos = []
        for grupo in grupos[:5]:  # Limitar a 5 vuelos
            vuelo = {}
            
            # Extraer detalles del viaje
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
                    escalas = escalas_elem.get_text(" ", strip=True).lower() if escalas_elem else "N/A"
                    duracion = duracion_elem.get_text(" ", strip=True) if duracion_elem else "N/A"
                
                origen_text = origen_div.get_text(" ", strip=True) if origen_div else "N/A"
                destino_text = destino_div.get_text(" ", strip=True) if destino_div else "N/A"
                
                vuelo["origen"] = origen_text.replace("h", " hs ") + (" min" if "min" not in origen_text else "")
                vuelo["destino"] = destino_text.replace("h", " hs ") + (" min" if "min" not in destino_text else "")
                vuelo["escalas"] = escalas
                vuelo["duracion"] = duracion

            # Extraer disponibilidad de asientos
            seat_info_div = grupo.find("div", class_="info-seat")
            vuelo["disponibles"] = seat_info_div.get_text(" ", strip=True).replace("!", "").strip() if seat_info_div else "N/A"

            # Extraer precios
            precios = []
            miles_group = grupo.find("div", class_="miles-group")
            if miles_group:
                precio_items = miles_group.find_all("li", class_="list-group-item")
                for item in precio_items:
                    texto_precio = item.get_text(" ", strip=True)
                    if texto_precio:
                        # Elimina etiquetas o palabras innecesarias y la palabra 'o'
                        texto_limpio = texto_precio.replace("Club Smiles", "").replace("Diamante", "")
                        texto_limpio = re.sub(r'\bo\b', '', texto_limpio).strip()
                        if "+" in texto_limpio:
                            partes = texto_limpio.split("+")
                            millas = partes[0].strip().split("x")[0].strip()
                            dinero = partes[1].strip().split("x")[0].strip()
                            precios.append(f"{millas} millas + {dinero}")
                        else:
                            millas = texto_limpio.split("x")[0].strip()
                            precios.append(f"{millas} millas")
            vuelo["precios"] = precios
            vuelos.append(vuelo)

        # Formatear los resultados
        mensajes = []
        date = date[-2:] + "/" + date[5:7] + "/" + date[:4]  # De "2025-12-06" a "06/12/2025"
        mensaje = ""
        for vuelo in vuelos:
            vuelo_info = (
                "✈️ Vuelo para el <b>" + date + "</b>\n"
                f"📍 • <b>Origen:</b> {html.escape(vuelo.get('origen', 'N/A'))}\n"
                f"📍 • <b>Destino:</b> {html.escape(vuelo.get('destino', 'N/A'))}\n"
                f"⏳ • <b>Duración:</b> {html.escape(vuelo.get('duracion', 'N/A'))}\n"
                f"🔁 • <b>Escalas:</b> {html.escape(vuelo.get('escalas', 'N/A'))}\n"
                f"💺 • <b>Asientos Disponibles:</b> {html.escape(vuelo.get('disponibles', 'N/A'))}\n"
                "💰 • <b>Precios:</b>\n<code>"
            )
            if vuelo.get("precios"):
                for prec in vuelo["precios"]:
                    vuelo_info += f" ▫️ {html.escape(prec)}\n"
            vuelo_info += "</code>\n"

            if len(mensaje) + len(vuelo_info) > 4096:  # Límite de Telegram
                mensajes.append(mensaje)
                mensaje = vuelo_info
            else:
                mensaje += vuelo_info

        if mensaje:
            mensajes.append(mensaje)

        print("[DEBUG] Listado de vuelos generado con éxito.")
        return mensajes if mensajes else ["No se encontró información en el listado."]

    except Exception as e:
        print(f"[DEBUG] Error al obtener datos: {e}")
        if retries > 0:
            print("[DEBUG] Reiniciando el navegador y reintentando...")
            restart_driver()
            return obtener_listado(driver, url, date, retries - 1)
        return [f"Error al obtener datos: {e}"]

def handle_message(update: Update, context: CallbackContext) -> None:
    global driver
    if is_locked():
        update.message.reply_text("⚠️ Another process is running. Please try again later.")
        return

    lock()
    try:
        message = update.message.text.split()
        if len(message) != 3:
            update.message.reply_text(
                "❌ Uso incorrecto. \n\n✈️ Debe tener 3 partes: origen (Buenos Aires: BUE), destino (Madrid: MAD) y la fecha (Formato DD/MM). \n\n👉 Por ejemplo: <code>BUE MAD 10/12</code>\n💡 <a href='https://es.wikipedia.org/wiki/Anexo:Aeropuertos_según_el_código_IATA'>Aprende los códigos de aeropuertos acá</a>",
                parse_mode='HTML'
            )
            return

        origin, destination, date = message
        origin = html.escape(origin.upper())
        destination = html.escape(destination.upper())

        if date.isdigit() and 1 <= int(date) <= 12:
            keyboard = [[InlineKeyboardButton(" 🛒 Adquiera el pack Premium  ", url="https://t.me/zantyy")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(
                f"😞 Lamentamos no tener las mejores ofertas para el <b>mes {html.escape(date.zfill(2))}</b> \n\n🎁 Tu suscripción solo permite buscar días. Con <b>Premium</b> podrías buscar todos los meses que quieras!",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return

        if re.match(r"^\d{2}-\d{2}$", date):
            pass
        elif re.match(r"^\d{4}$", date):
            date = f"{date[:2]}-{date[2:]}"
        elif re.match(r"^\d{1,2}/\d{1,2}$", date):
            day, month = date.split('/')
            date = f"{month.zfill(2)}-{day.zfill(2)}"
        else:
            update.message.reply_text(
                "❌ Uso incorrecto. \n\n✈️ Debe tener 3 partes: origen (Buenos Aires: BUE), destino (Madrid: MAD) y la fecha (Formato DD/MM). \n\n👉 Por ejemplo: <code>BUE MAD 10/12</code>\n💡 <a href='https://es.wikipedia.org/wiki/Anexo:Aeropuertos_según_el_código_IATA'>Aprende los códigos de aeropuertos acá</a>",
                parse_mode='HTML'
            )
            return

        date = f"{DEFAULT_YEAR}-{html.escape(date)}"
        url = generate_url(origin, destination, date)
        update.message.reply_text("⌛ Esperá! Obteniendo resultados desde la URL: " + html.escape(url), parse_mode='HTML')
        print(f"[DEBUG] Pedido de {update.message.from_user.username} desde {origin} a {destination} el {date}.")

        # Inicializar el navegador solo si no está activo
        if driver is None:
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
    """Initialize and run the Telegram bot."""
    global driver
    clean_temp_folders()  # Limpiar solo al inicio
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()
    # Limpiar recursos al cerrar
    if driver is not None:
        driver.quit()
    clean_temp_folders()

if __name__ == "__main__":
    main()
