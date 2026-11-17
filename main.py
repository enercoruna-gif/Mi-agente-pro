import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from browser_use import Browser
from langchain_google_genai import ChatGoogleGenerativeAI

# Configurar logs detallados
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GH_TOKEN = os.getenv("GH_TOKEN")
GH_REPO = os.getenv("GH_REPO")
COOKIES_FILE = "cookies.json"

def cargar_cookies_desde_github():
    if not GH_TOKEN or not GH_REPO:
        logging.info("No se han configurado GH_TOKEN o GH_REPO. Saltando carga de cookies.")
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
        else:
            logging.warning(f"No se pudieron descargar cookies (Código HTTP: {r.status_code})")
    except Exception as e:
        logging.error(f"Error al descargar cookies: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        await update.message.reply_text("No tienes autorización para usar este bot.")
        return
    await update.message.reply_text("¡Sistema operativo y listo! El agente está en línea.")

def main():
    if not TELEGRAM_TOKEN:
        logging.critical("¡ERROR CRÍTICO! Falta el TELEGRAM_TOKEN en las variables de entorno de Render.")
        return

    logging.info("Iniciando servicios del bot...")
    cargar_cookies_desde_github()

    # Comprobación de la clave de Gemini
    if not GEMINI_API_KEY:
        logging.warning("Advertencia: GEMINI_API_KEY no está definida.")

    # Inicialización del bot de Telegram
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    logging.info("Bot de Telegram configurado correctamente. Iniciando polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
