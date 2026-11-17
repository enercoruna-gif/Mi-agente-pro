import os
import logging
import json
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
MEMORY_FILE = "empresa_memoria.json"
CHAT_HISTORY_FILE = "chat_history.json"

# --- DICCIONARIO DE MODELOS DE TRES NIVELES ---
AVAILABLE_MODELS = {
    "lite": "gemini-2.5-flash-lite",   # Para análisis rápido, chat fluido y bajo consumo
    "flash": "gemini-flash",       # Para razonamiento estándar y decisiones lógicas
    "pro": "gemini-pro"            # Para programación pesada y creación de webs
}

current_model_key = "lite"

empresa_memoria = {}
historial_conversacion = []

def obtener_llm_activo():
    model_name = AVAILABLE_MODELS.get(current_model_key, "gemini-flash")
    return ChatGoogleGenerativeAI(model=model_name, google_api_key=GEMINI_API_KEY)

def cargar_datos():
    global empresa_memoria, historial_conversacion
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                empresa_memoria = json.load(f)
        except Exception as e:
            logging.error(f"Error al leer memoria corporativa: {e}")
            
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                historial_conversacion = json.load(f)
        except Exception as e:
            logging.error(f"Error al leer historial de chat: {e}")

def guardar_datos():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(empresa_memoria, f, ensure_ascii=False, indent=4)
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(historial_conversacion[-20:], f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error al guardar datos en disco: {e}")

def cargar_cookies_desde_github():
    if not GH_TOKEN or not GH_REPO:
        logging.info("GH_TOKEN o GH_REPO no configurados. Saltando descarga de cookies.")
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
            logging.warning(f"No se pudieron descargar cookies de GitHub (Código: {r.status_code}).")
    except Exception as e:
        logging.error(f"Error al descargar cookies: {e}")

# --- FUNCIÓN PARA INYECTAR COOKIES EN PLAYWRIGHT ---
async def inyectar_cookies_si_existen(browser_instance):
    """Inyecta las cookies de cookies.json en la sesión activa de browser-use"""
    if not os.path.exists(COOKIES_FILE):
        logging.info("No se encontró el archivo cookies.json para inyectar.")
        return
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        
        if hasattr(browser_instance, "get_current_page"):
            page = await browser_instance.get_current_page()
            if page and hasattr(page, "context"):
                await page.context.add_cookies(cookies)
                logging.info(f"✅ {len(cookies)} cookies de Google inyectadas con éxito.")
    except Exception as e:
        logging.error(f"Error al inyectar cookies en el navegador: {e}")

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        await update.message.reply_text("No tienes autorización para usar este bot.")
        return
    await update.message.reply_text(
        f"🤖 **¡Asistente Grok & Cookies Activo!**\n"
        f"• Modelo actual: *{current_model_key.upper()}*\n\n"
        f"💬 Háblame con total normalidad. Mantengo el hilo de chat, memorizo datos clave de tu empresa y navego por web usando tu cuenta de Google.\n\n"
        f"📋 **Comandos:** `/memoria`, `/olvidar <clave>`, `/modelo [lite|flash|pro]`"
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
            f"Dis
