# Instructivo para Instalar y Configurar el Bot de Telegram

Este documento describe los pasos necesarios para instalar y configurar todas las dependencias del bot de Telegram que consulta ofertas de Smiles en Ubuntu 22.04.

---

## **Requisitos Previos**

Antes de comenzar, asegúrate de contar con lo siguiente:

- Ubuntu 22.04 instalado.
- Acceso a una terminal con privilegios de superusuario.
- Token de bot de Telegram (proporcionado por [BotFather](https://core.telegram.org/bots)).

---

## **1. Actualizar el sistema**

Primero, actualiza los paquetes del sistema:

```bash
sudo apt update && sudo apt upgrade -y
```

---

## **2. Instalar Python y pip**

Ubuntu 22.04 incluye Python 3.10 por defecto. Asegúrate de instalarlo junto con pip:

```bash
sudo apt install python3 python3-pip -y
```

Verifica las versiones instaladas:

```bash
python3 --version
pip3 --version
```

---

## **3. Instalar Google Chrome**

Selenium requiere Google Chrome para simular un navegador.

1. **Descargar e instalar Google Chrome:**

   ```bash
   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
   sudo apt install ./google-chrome-stable_current_amd64.deb
   ```

2. **Verificar la instalación:**

   ```bash
   google-chrome --version
   ```

---

## **4. Instalar ChromeDriver**

ChromeDriver permite a Selenium controlar Google Chrome. Descarga la versión compatible con tu navegador:

1. **Identificar la versión de Google Chrome:**

   ```bash
   google-chrome --version
   ```

   Por ejemplo, si la versión es `131.0.6778.204`, necesitas ChromeDriver 131.

2. **Descargar y configurar ChromeDriver:**

   ```bash
   wget https://chromedriver.storage.googleapis.com/131.0.6778.204/chromedriver_linux64.zip
   unzip chromedriver_linux64.zip
   sudo mv chromedriver /usr/local/bin/
   ```

3. **Verificar la instalación:**

   ```bash
   chromedriver --version
   ```

---

## **5. Instalar las dependencias de Python**

Instala las bibliotecas necesarias:

```bash
pip3 install selenium python-telegram-bot==13.15
```

---

## **6. Crear el archivo del bot**

1. **Crear el archivo:**

   ```bash
   nano telegram_bot.py
   ```

2. **Pegar el código:**

   Copia el código del bot en el archivo y reemplaza `YOUR_TELEGRAM_BOT_TOKEN` con tu token de Telegram.

3. **Guardar y salir:**

   - Presiona `Ctrl + O` para guardar.
   - Presiona `Ctrl + X` para salir.

---

## **7. Ejecutar el bot**

Ejecuta el bot desde la terminal:

```bash
python3 telegram_bot.py
```

---

## **8. Automatizar el inicio del bot (opcional)**

Para que el bot se ejecute automáticamente al iniciar el sistema, crea un servicio de systemd:

1. **Crear el archivo del servicio:**

   ```bash
   sudo nano /etc/systemd/system/telegram_bot.service
   ```

2. **Agregar el contenido:**

   ```ini
   [Unit]
   Description=Telegram Bot
   After=network.target

   [Service]
   User=YOUR_USERNAME
   WorkingDirectory=/path/to/your/bot
   ExecStart=/usr/bin/python3 /path/to/your/bot/telegram_bot.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Reemplaza:
   - `YOUR_USERNAME` con tu nombre de usuario en Ubuntu.
   - `/path/to/your/bot` con la ruta completa al archivo `telegram_bot.py`.

3. **Habilitar y arrancar el servicio:**

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram_bot
   sudo systemctl start telegram_bot
   sudo systemctl status telegram_bot
   ```

---

## **9. Verificar el bot**

Abre Telegram, envía mensajes al bot y verifica que responda correctamente. Ejemplo:

```plaintext
EZE MAD 2024-05
```

---

## **10. Solución de problemas comunes**

- **Error: `chromedriver` no encontrado:**
  - Verifica que `chromedriver` esté en `/usr/local/bin/` y sea ejecutable.

  ```bash
  which chromedriver
  chmod +x /usr/local/bin/chromedriver
  ```

- **El bot no responde:**
  - Verifica que el token del bot sea correcto.
  - Consulta los logs del bot:

    ```bash
    journalctl -u telegram_bot.service -f
    ```

