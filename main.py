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

# --- DICCIONARIO DE MODELOS DE TRES NIVELES ---
AVAILABLE_MODELS = {
    "lite": "gemini-2.5-flash-lite",   # Para tareas repetitivas de bajo consumo y análisis de memoria
    "flash": "gemini-flash",       # Para razonamiento estándar y decisiones lógicas
    "pro": "gemini-pro"            # Para programación pesada y creación de webs
}

# Estado global para recordar qué modelo está activo (arranca por defecto en "lite")
current_model_key = "lite"

# Memoria corporativa en RAM
empresa_memoria = {}

def obtener_llm_activo():
    model_name = AVAILABLE_MODELS.get(current_model_key, "gemini-flash")
    return ChatGoogleGenerativeAI(model=model_name, google_api_key=GEMINI_API_KEY)

# --- SISTEMA DE MEMORIA PERSISTENTE ---
def cargar_memoria():
    global empresa_memoria
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                empresa_memoria = json.load(f)
            logging.info("Memoria corporativa cargada localmente.")
        except Exception as e:
            logging.error(f"Error al leer memoria local: {e}")

def guardar_memoria_disco():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(empresa_memoria, f, ensure_ascii=False, indent=4)
        logging.info("Memoria corporativa guardada en disco.")
    except Exception as e:
        logging.error(f"Error al guardar memoria: {e}")

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

# --- COMANDOS BÁSICOS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        await update.message.reply_text("No tienes autorización para usar este bot.")
        return
    await update.message.reply_text(
        f"🚀 **¡Sistema Autónoma de Empresa Listo!**\n"
        f"• Modelo activo: *{current_model_key.upper()}*\n\n"
        f"💡 **Cómo funciona:** Habla conmigo con total normalidad. Si me das datos importantes, directrices o plantillas, **los recordaré automáticamente para siempre**.\n\n"
        f"📋 **Comandos útiles:**\n"
        f"• `/memoria` - Ver todo lo que tengo guardado sobre tu empresa.\n"
        f"• `/olvidar <clave>` - Borrar un dato específico.\n"
        f"• `/modelo [lite|flash|pro]` - Cambiar de modelo al vuelo."
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
    else:
        await update.message.reply_text("❌ Modelo no reconocido. Usa `/modelo lite`, `/modelo flash` o `/modelo pro`.")

async def ver_memoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        return

    if not empresa_memoria:
        await update.message.reply_text("📂 La memoria corporativa está vacía actualmente.")
        return

    texto = "📂 **Memoria Corporativa Actual:**\n\n"
    for k, v in empresa_memoria.items():
        texto += f"• **{k}**: {v}\n\n"
    await update.message.reply_text(texto)

async def olvidar_memoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        return

    if not context.args:
        await update.message.reply_text("❌ Indica qué clave quieres borrar. Uso: `/olvidar <clave>`")
        return

    clave = context.args[0].lower()
    if clave in empresa_memoria:
        del empresa_memoria[clave]
        guardar_memoria_disco()
        await update.message.reply_text(f"🗑️ Clave `{clave}` eliminada de la memoria.")
    else:
        await update.message.reply_text(f"⚠️ No se encontró la clave `{clave}` en la memoria.")

# --- PROCESAMIENTO INTELIGENTE Y AUTÓNOMO DE MENSAJES ---
async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        return

    texto_usuario = update.message.text

    # 1. Analizar de forma autónoma si el mensaje contiene información corporativa a recordar
    try:
        analizador_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=GEMINI_API_KEY)
        prompt_analisis = f"""
        Analiza el siguiente mensaje del usuario. Determina si contiene información clave de su empresa, directrices de gestión, tonos de voz, datos de contacto o plantillas de correo que deba recordar para el futuro.
        
        Si NO contiene información relevante para guardar, responde exactamente con la palabra: NADA.
        Si SÍ contiene información, devuélvela estrictamente en formato JSON válido de una sola línea con una clave descriptiva corta y el contenido, así:
        {{"clave": "nombre_corto_del_dato", "contenido": "el texto completo a recordar"}}

        Mensaje del usuario: "{texto_usuario}"
        """
        
        respuesta_analisis = analizador_llm.invoke(prompt_analisis).content.strip()
        
        if "NADA" not in respuesta_analisis:
            # Limpiar posible formato de código markdown si el modelo lo añade
            respuesta_limpia = respuesta_analisis.replace("```json", "").replace("```", "").strip()
            datos_json = json.loads(respuesta_limpia)
            
            clave = datos_json.get("clave")
            contenido = datos_json.get("contenido")
            
            if clave and contenido:
                empresa_memoria[clave] = contenido
                guardar_memoria_disco()
                await update.message.reply_text(f"💾 *[Memorizado automáticamente]* -> Guardado en `{clave}`")
    except Exception as e:
        logging.error(f"Error en auto-memoria: {e}")

    # 2. Ejecutar la tarea de navegación o respuesta aplicando todo el contexto corporativo acumulado
    await update.message.reply_text(f"🔍 Procesando con el modelo *{current_model_key.upper()}* aplicando contexto empresarial...")

    try:
        contexto_corporativo = "CONTEXTO DE LA EMPRESA Y DIRECTRICES:\n"
        if empresa_memoria:
            for k, v in empresa_memoria.items():
                contexto_corporativo += f"- {k}: {v}\n"
        else:
            contexto_corporativo += "No hay directrices especiales guardadas todavía.\n"

        tarea_con_contexto = f"{contexto_corporativo}\nPETICIÓN DEL USUARIO:\n{texto_usuario}"

        llm_actual = obtener_llm_activo()

        browser = Browser(
            headless=False,
            extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        agent = Agent(
            task=tarea_con_contexto,
            browser=browser,
            llm=llm_actual
        )
        
        result = await agent.run()
        await update.message.reply_text(f"✨ **Resultado:**\n\n{result}")

    except Exception as e:
        logging.error(f"Error al ejecutar el agente: {e}")
        await update.message.reply_text(f"❌ Error al ejecutar la tarea: {e}")

def main():
    if not TELEGRAM_TOKEN:
        logging.critical("¡ERROR CRÍTICO! Falta el TELEGRAM_TOKEN en las variables de entorno.")
        return

    logging.info("Iniciando servicios del bot...")
    cargar_cookies_desde_github()
    cargar_memoria()

    if not GEMINI_API_KEY:
        logging.warning("Advertencia: GEMINI_API_KEY no está definida.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Registro de manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("modelo", cambiar_modelo))
    app.add_handler(CommandHandler("memoria", ver_memoria))
    app.add_handler(CommandHandler("olvidar", olvidar_memoria))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), manejar_mensaje))

    logging.info("Bot autónomo con memoria inteligente iniciado en modo polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
