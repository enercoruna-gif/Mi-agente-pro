import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from browser_use import Browser, Agent
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

# --- DICCIONARIO DE MODELOS DE TRES NIVELES ---
AVAILABLE_MODELS = {
    "lite": "gemini-2.5-flash-lite",   # Para tareas repetitivas de bajo consumo (Gmail, scraping)
    "flash": "gemini-flash",       # Para razonamiento estándar y decisiones lógicas
    "pro": "gemini-pro"            # Para programación pesada y creación de webs
}

# Estado global para recordar qué modelo está activo (arranca por defecto en "lite")
current_model_key = "lite"

def obtener_llm_activo():
    model_name = AVAILABLE_MODELS.get(current_model_key, "gemini-flash")
    return ChatGoogleGenerativeAI(model=model_name, google_api_key=GEMINI_API_KEY)

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
    await update.message.reply_text(
        f"🚀 **¡Sistema operativo y listo!**\n"
        f"• Modelo activo: *{current_model_key.upper()}*\n\n"
        f"Comandos disponibles:\n"
        f"• `/modelo [lite|flash|pro]` - Cambiar de modelo al vuelo\n"
        f"• Envía cualquier tarea para que el agente navegue."
    )

async def cambiar_modelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_model_key
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        return

    if not context.args:
        modelos_str = ", ".join(AVAILABLE_MODELS.keys())
        await update.message.reply_text(
            f"ℹ️ Modelo actual: *{current_model_key.upper()}*\n"
            f"Disponibles: {modelos_str}\n"
            f"Uso: `/modelo lite`, `/modelo flash` o `/modelo pro`"
        )
        return

    nuevo_modelo = context.args[0].lower()
    if nuevo_modelo in AVAILABLE_MODELS:
        current_model_key = nuevo_modelo
        await update.message.reply_text(f"✅ ¡Modelo cambiado con éxito a: *{current_model_key.upper()}*!")
        logging.info(f"El usuario cambió el modelo activo a: {current_model_key}")
    else:
        await update.message.reply_text("❌ Modelo no reconocido. Usa `/modelo lite`, `/modelo flash` o `/modelo pro`.")

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        return

    texto_tarea = update.message.text
    await update.message.reply_text(f"🔍 Procesando tarea con el modelo *{current_model_key.upper()}*...")

    try:
        # Instanciar el LLM correspondiente al modelo seleccionado en este momento
        llm_actual = obtener_llm_activo()

        # Inicialización compatible con browser-use 1.0
        browser = Browser(
            headless=False,
            extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        agent = Agent(
            task=texto_tarea,
            browser=browser,
            llm=llm_actual
        )
        
        result = await agent.run()
        await update.message.reply_text(f"✨ **Tarea completada:**\n\n{result}")

    except Exception as e:
        logging.error(f"Error al ejecutar el agente: {e}")
        await update.message.reply_text(f"❌ Error al ejecutar la tarea: {e}\n\n*(Si ha requerido un captcha, recuerda revisarlo en el puerto noVNC 10000)*")

def main():
    if not TELEGRAM_TOKEN:
        logging.critical("¡ERROR CRÍTICO! Falta el TELEGRAM_TOKEN en las variables de entorno.")
        return

    logging.info("Iniciando servicios del bot...")
    cargar_cookies_desde_github()

    if not GEMINI_API_KEY:
        logging.warning("Advertencia: GEMINI_API_KEY no está definida.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Registro de manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("modelo", cambiar_modelo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), manejar_mensaje))

    logging.info("Bot de Telegram configurado correctamente. Iniciando polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
