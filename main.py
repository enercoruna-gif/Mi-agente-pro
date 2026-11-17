import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from browser_use import Agent, Browser
from langchain_google_genai import ChatGoogleGenerativeAI
import requests

# Configurar logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GH_TOKEN = os.getenv("GH_TOKEN")
GH_REPO = os.getenv("GH_REPO") # Formato: usuario/repositorio-memoria
COOKIES_FILE = "cookies.json"

def cargar_cookies_desde_github():
    if not GH_TOKEN or not GH_REPO:
        return
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{COOKIES_FILE}"
        headers = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            import base64
            content = base64.b64decode(r.json()["content"])
            with open(COOKIES_FILE, "wb") as f:
                f.write(content)
            logging.info("Cookies descargadas de GitHub con éxito.")
    except Exception as e:
        logging.error(f"Error al descargar cookies: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        await update.message.reply_text("No tienes autorización para usar este bot.")
        return
    await update.message.reply_text("¡Sistema operativo y listo! Envíame una tarea o comando.")

def main():
    if not TELEGRAM_TOKEN:
        logging.error("Falta el TELEGRAM_TOKEN en las variables de entorno.")
        return

    # Cargar cookies antes de iniciar
    cargar_cookies_desde_github()

    # Configurar el modelo de lenguaje con Google AI Studio
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GEMINI_API_KEY)

    # Inicializar navegador adaptado a browser-use 1.0 (sin BrowserConfig)
    browser = Browser(
        headless=False,
        cookies_file=COOKIES_FILE,
        extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"]
    )

    # Iniciar bot de Telegram
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    logging.info("Bot de Telegram iniciado correctamente en modo polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
