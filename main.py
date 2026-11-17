import os
import logging
import json
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
COOKIES_FILE = "cookies.json"
MEMORY_FILE = "empresa_memoria.json"
CHAT_HISTORY_FILE = "chat_history.json"

# --- DICCIONARIO DE MODELOS VIGENTES ---
AVAILABLE_MODELS = {
    "lite": "gemini-3.8-flash",
    "flash": "gemini-3.8-flash",
    "pro": "gemini-pro"
}

current_model_key = "lite"

empresa_memoria = {}
historial_conversacion = []

def obtener_llm_activo():
    model_name = AVAILABLE_MODELS.get(current_model_key, "gemini-3.8-flash")
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

# --- VERIFICACIÓN LOCAL DE COOKIES ---
def verificar_cookies_locales():
    if os.path.exists(COOKIES_FILE):
        logging.info("✅ Archivo cookies.json detectado localmente en el proyecto.")
    else:
        logging.warning("⚠️ No se encuentra el archivo cookies.json en la ruta local.")

async def inyectar_cookies_si_existen(browser_instance):
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        await update.message.reply_text("No tienes autorización para usar este bot.")
        return
    await update.message.reply_text(
        "🤖 **¡Asistente Grok & Cookies Activo!**\n"
        f"• Modelo actual: *{current_model_key.upper()}*\n\n"
        "💬 Háblame con total normalidad. Mantengo el hilo de chat, memorizo datos clave y navego usando tu sesión de Google (`enercoruna`).\n\n"
        "📋 **Comandos:** `/memoria`, `/olvidar <clave>`, `/modelo [lite|flash|pro]`"
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
            "Uso: `/modelo lite`, `/modelo flash` o `/modelo pro`"
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
        guardar_datos()
        await update.message.reply_text(f"🗑️ Clave `{clave}` eliminada de la memoria.")
    else:
        await update.message.reply_text(f"⚠️ No se encontró la clave `{clave}` en la memoria.")

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        return

    texto_usuario = update.message.text
    respuesta_bot = "Error procesando la solicitud."

    try:
        analizador_llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", google_api_key=GEMINI_API_KEY)
        prompt_analisis = f"""
        Analiza el mensaje del usuario. Si contiene información clave de su empresa, directrices o plantillas a recordar, responde estrictamente en JSON: {{"clave": "nombre_corto", "contenido": "texto"}}
        Si no hay nada relevante, responde exactamente: NADA.
        Mensaje: "{texto_usuario}"
        """
        resp_analisis = analizador_llm.invoke(prompt_analisis).content.strip()
        if "NADA" not in resp_analisis:
            resp_limpia = resp_analisis.replace("```json", "").replace("```", "").strip()
            datos_json = json.loads(resp_limpia)
            if datos_json.get("clave") and datos_json.get("contenido"):
                empresa_memoria[datos_json.get("clave")] = datos_json.get("contenido")
                guardar_datos()
                await update.message.reply_text(f"💾 *[Memorizado]* -> `{datos_json.get('clave')}`")
    except Exception as e:
        logging.error(f"Error en auto-memoria: {e}")

    try:
        router_llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", google_api_key=GEMINI_API_KEY)
        prompt_router = f"""
        Clasifica la petición en: NAVEGACION (si pide entrar a una web, buscar leads, hacer acciones visuales) o CHAT (si es charla, redactar correos o estrategia).
        Responde SOLAMENTE NAVEGACION o CHAT.
        Petición: "{texto_usuario}"
        """
        tipo_accion = router_llm.invoke(prompt_router).content.strip().upper()
    except Exception:
        tipo_accion = "CHAT"

    contexto_corporativo = "DIRECTRICES EMPRESARIALES:\n" + (json.dumps(empresa_memoria, ensure_ascii=False) if empresa_memoria else "Ninguna")
    historial_reciente = "\n".join([f"{h['rol']}: {h['texto']}" for h in historial_conversacion[-6:]])

    llm_actual = obtener_llm_activo()

    if "NAVEGACION" in tipo_accion:
        await update.message.reply_text(f"🌐 [Modo Navegación] Arrancando con *{current_model_key.upper()}* y aplicando sesión de Google...")
        try:
            tarea_completa = f"{contexto_corporativo}\n\nHISTORIAL RECIENTE:\n{historial_reciente}\n\nTAREA WEB:\n{texto_usuario}"
            
            browser = Browser(headless=False, extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"])
            agent = Agent(task=tarea_completa, browser=browser, llm=llm_actual)
            
            await inyectar_cookies_si_existen(browser)

            result = await agent.run()
            respuesta_bot = str(result)
            await update.message.reply_text(f"✨ **Resultado web:**\n\n{respuesta_bot}")
        except Exception as e:
            logging.error(f"Error en navegador: {e}")
            respuesta_bot = f"❌ Error ejecutando la tarea web: {e}"
            await update.message.reply_text(respuesta_bot)
    else:
        await update.message.reply_text(f"💭 Pensando con *{current_model_key.upper()}*...")
        try:
            prompt_chat = f"""
            Eres un asistente ejecutivo y de estrategia empresarial avanzado (estilo Grok).
            {contexto_corporativo}
            HISTORIAL:
            {historial_reciente}
            USUARIO:
            {texto_usuario}
            """
            respuesta_bot = llm_actual.invoke(prompt_chat).content
            await update.message.reply_text(respuesta_bot)
        except Exception as e:
            logging.error(f"Error en chat: {e}")
            respuesta_bot = f"❌ Error: {e}"
            await update.message.reply_text(respuesta_bot)

    historial_conversacion.append({"rol": "Usuario", "texto": texto_usuario})
    historial_conversacion.append({"rol": "Asistente", "texto": respuesta_bot})
    guardar_datos()

def main():
    if not TELEGRAM_TOKEN:
        logging.critical("¡Falta el TELEGRAM_TOKEN!")
        return

    logging.info("Iniciando bot...")
    verificar_cookies_locales()
    cargar_datos()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("modelo", cambiar_modelo))
    app.add_handler(CommandHandler("memoria", ver_memoria))
    app.add_handler(CommandHandler("olvidar", olvidar_memoria))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), manejar_mensaje))

    app.run_polling()

if __name__ == "__main__":
    main()
