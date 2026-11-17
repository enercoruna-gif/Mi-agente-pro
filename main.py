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

# Estado global del modelo activo (arranca por defecto en "lite")
current_model_key = "lite"

# Diccionarios en memoria RAM
empresa_memoria = {}
historial_conversacion = []  # Almacena las últimas interacciones para dar contexto de chat

def obtener_llm_activo():
    model_name = AVAILABLE_MODELS.get(current_model_key, "gemini-flash")
    return ChatGoogleGenerativeAI(model=model_name, google_api_key=GEMINI_API_KEY)

# --- PERSISTENCIA (MEMORIA Y CHAT) ---
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
            json.dump(historial_conversacion[-20:], f, ensure_ascii=False, indent=4) # Guardar los últimos 20 turns
    except Exception as e:
        logging.error(f"Error al guardar datos en disco: {e}")

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

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        await update.message.reply_text("No tienes autorización para usar este bot.")
        return
    await update.message.reply_text(
        f"🤖 **¡Asistente Estilo Grok & Agente Web Listo!**\n"
        f"• Modelo activo: *{current_model_key.upper()}*\n\n"
        f"💬 **Cómo interactuar:** Háblame con total normalidad. Mantengo el hilo de la conversación, aprendo de tu empresa automáticamente y ejecuto tareas web si me lo pides.\n\n"
        f"📋 **Comandos útiles:**\n"
        f"• `/memoria` - Ver directrices guardadas sobre tu empresa.\n"
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
        guardar_datos()
        await update.message.reply_text(f"🗑️ Clave `{clave}` eliminada de la memoria.")
    else:
        await update.message.reply_text(f"⚠️ No se encontró la clave `{clave}` en la memoria.")

# --- PROCESAMIENTO INTELIGENTE (ESTILO GROK + NAVEGACIÓN) ---
async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ALLOWED_USER_ID and user_id != str(ALLOWED_USER_ID):
        return

    texto_usuario = update.message.text

    # 1. Auto-aprender información corporativa si el usuario la menciona
    try:
        analizador_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=GEMINI_API_KEY)
        prompt_analisis = f"""
        Analiza el siguiente mensaje del usuario. Determina si contiene información clave de su empresa, directrices de gestión, tonos de voz, datos de contacto o plantillas de correo que deba recordar para el futuro.
        Si NO contiene información relevante, responde exactamente con la palabra: NADA.
        Si SÍ contiene información, devuélvela estrictamente en formato JSON válido de una sola línea: {{"clave": "nombre_corto", "contenido": "texto a recordar"}}
        Mensaje: "{texto_usuario}"
        """
        resp_analisis = analizador_llm.invoke(prompt_analisis).content.strip()
        if "NADA" not in resp_analisis:
            resp_limpia = resp_analisis.replace("```json", "").replace("```", "").strip()
            datos_json = json.loads(resp_limpia)
            if datos_json.get("clave") and datos_json.get("contenido"):
                empresa_memoria[datos_json.get("clave")] = datos_json.get("contenido")
                guardar_datos()
                await update.message.reply_text(f"💾 *[Memorizado automáticamente]* -> `{datos_json.get('clave')}`")
    except Exception as e:
        logging.error(f"Error en auto-memoria: {e}")

    # 2. Determinar si el mensaje requiere navegar por la web o es una consulta conversacional/chat puro
    try:
        router_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=GEMINI_API_KEY)
        prompt_router = f"""
        Clasifica la siguiente petición del usuario en una de estas dos categorías exactas:
        - NAVEGACION (si pide explícitamente entrar a una web, buscar empresas, hacer scraping, enviar correos automatizados en una plataforma o interactuar con una interfaz visual web).
        - CHAT (si es una pregunta, redacción de textos, debate, consulta de estrategia o conversación general que no requiere abrir el navegador).
        Responde SOLAMENTE con la palabra NAVEGACION o CHAT.
        Petición: "{texto_usuario}"
        """
        tipo_accion = router_llm.invoke(prompt_router).content.strip().upper()
    except Exception:
        tipo_accion = "CHAT"

    # Preparar el contexto corporativo y el historial reciente de chat
    contexto_corporativo = "DIRECTRICES EMPRESARIALES:\n" + (json.dumps(empresa_memoria, ensure_ascii=False) if empresa_memoria else "Ninguna")
    historial_reciente = "\n".join([f"{h['rol']}: {h['texto']}" for h in historial_conversacion[-6:]])

    llm_actual = obtener_llm_activo()

    if "NAVEGACION" in tipo_accion:
        await update.message.reply_text(f"🌐 [Modo Navegación] Ejecutando tarea con *{current_model_key.upper()}*...")
        try:
            tarea_completa = f"{contexto_corporativo}\n\nHISTORIAL RECIENTE:\n{historial_reciente}\n\nTAREA WEB A EJECUTAR:\n{texto_usuario}"
            
            browser = Browser(headless=False, extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"])
            agent = Agent(task=tarea_completa, browser=browser, llm=llm_actual)
            result = await agent.run()
            
            respuesta_bot = str(result)
            await update.message.reply_text(f"✨ **Resultado web:**\n\n{respuesta_bot}")
        except Exception as e:
            logging.error(f"Error en navegador: {e}")
            await update.message.reply_text(f"❌ Error ejecutando la tarea web: {e}")
    else:
        # Modo Chat conversacional puro (estilo Grok instantáneo)
        await update.message.reply_text(f"💭 Pensando con *{current_model_key.upper()}*...")
        try:
            prompt_chat = f"""
            Eres un asistente ejecutivo y de estrategia empresarial avanzado, inteligente y directo (estilo Grok).
            {contexto_corporativo}
            
            HISTORIAL DE CONVERSACIÓN RECIENTE:
            {historial_reciente}
            
            NUEVO MENSAJE DEL USUARIO:
            {texto_usuario}
            """
            respuesta_bot = llm_actual.invoke(prompt_chat).content
            await update.message.reply_text(respuesta_bot)
        except Exception as e:
            logging.error(f"Error en chat: {e}")
            await update.message.reply_text(f"❌ Error procesando el mensaje: {e}")

    # Guardar en el historial de chat persist
