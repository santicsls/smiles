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

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_YEAR = int(os.getenv("DEFAULT_YEAR", "2025"))
SELENIUM_TIMEOUT = 30  # Timeout in seconds for page loading
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

def format_table_markdown(html_content):
    """
    Convert HTML table content to Markdown format, ensuring correct airline-price pairing.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    markdown_text = ""

    if not table:
        return "No table found in the content."

    rows = table.find_all('tr')
    
    # Extract airline names from the header row
    airline_names = []
    header_cells = rows[0].find_all(['th', 'td'])
    for td in header_cells[1:]:  # Start from index 1 to skip the "Compañía Aérea" header
        span = td.find('span')
        if span:
            airline_names.append(span.get_text(strip=True))

    # Process each row for flight types and prices
    for row in rows[1:]:
        cells = row.find_all(['th', 'td'])
        flight_type = cells[0].get_text(strip=True) if cells else "Unknown"
        
        # Prices are in the same order as airlines in the header
        price_texts = [cell.get_text(strip=True) for cell in cells[1:] if cell.get_text(strip=True)]

        # Combine airlines with prices, ensuring alignment
        pairs = list(zip(airline_names, price_texts))
        
        if not price_texts:
            markdown_text += f"{flight_type}: Ninguno\n\n"
        else:
            markdown_text += f"{flight_type}\n"
            for airline, price in pairs:
                if price:
                    markdown_text += f" ▪️ {airline}: ${price}\n"
            markdown_text += "\n"

    return markdown_text.strip() if markdown_text else "No valid flight data found."

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

def wait_for_page_load(driver, url):
    """
    Navigate to URL, collect initial data, click to update, wait, then collect updated data.

    :param driver: Selenium WebDriver instance
    :param url: URL to navigate to
    :return: Combined HTML content of both table states or error message
    """
    driver.get(url)
    try:
        # Wait for the initial table to load
        WebDriverWait(driver, SELENIUM_TIMEOUT).until(
            EC.presence_of_element_located((By.CLASS_NAME, "resume-filters"))
        )

        # Capture the initial table data
        initial_content = driver.page_source
        soup_initial = BeautifulSoup(initial_content, "html.parser")
        table_initial = soup_initial.find("div", class_="resume-filters").find("table")

        if not table_initial:
            return "No initial table data found."

        # Click on the element to update the table
        try:
            clickable_element = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "table-nav.purple-nav"))
            )
            clickable_element.click()
            
            # Wait for 5 seconds to ensure the page updates
            time.sleep(5)

            # Capture the updated table data
            updated_content = driver.page_source
            soup_updated = BeautifulSoup(updated_content, "html.parser")
            table_updated = soup_updated.find("div", class_="resume-filters").find("table")

            if not table_updated:
                print("No updated table data found after click.")
                return table_initial.prettify()

            # Combine initial and updated data
            return table_initial.prettify() + "\n\n" + table_updated.prettify()

        except (NoSuchElementException, StaleElementReferenceException) as e:
            print(f"Click action failed: {e}")
            return table_initial.prettify()

    except TimeoutException:
        return f"Error loading the page with Selenium: Timeout after {SELENIUM_TIMEOUT} seconds."

def handle_message(update: Update, context: CallbackContext) -> None:
    """
    Handle incoming messages from Telegram, manage lock to prevent concurrent executions.
    """
    if is_locked():
        update.message.reply_text("⚠️ Another process is running. Please try again later.")
        return

    lock()
    try:
        message = update.message.text.split()
        if len(message) != 3:
            update.message.reply_text(
                "❌ Incorrect usage. \n\n✈️ Must have 3 parts: origin (Ezeiza: EZE), destination (Madrid: MAD), and date (Format YYYY-MM-DD). \n\n👉 EZE MAD 2025-12"
            )
            return

        origin, destination, date = message
        if date.isdigit() and len(date) == 2:
            date = f"{DEFAULT_YEAR}-{date.zfill(2)}"

        url = generate_url(origin, destination, date)
        update.message.reply_text(
            f"✅ New request loaded:\n\n✈️ Origin: {origin}\n✈️ Destination: {destination}\n✈️ Date: {date}\n\n🌐 URL: {url}\n\n⌛ Getting results..."
        )

        driver = setup_driver()
        page_content = wait_for_page_load(driver, url)
        driver.quit()

        with open("1.html", "w", encoding="utf-8") as file:
            file.write(page_content)
        with open("1.html", "rb") as file:
            update.message.reply_document(document=file, filename="1.html")

        update.message.reply_text(format_table_markdown(page_content))

    except Exception as e:
        update.message.reply_text(f"Error processing the message: {e}")
    finally:
        unlock()

def main():
    """
    Initialize and run the Telegram bot.
    """
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
