import os
import re
import time
import hashlib
import base64
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig

# --- VARIABLES DE ENTORNO ---
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GH_TOKEN = os.environ["GH_TOKEN"]
GH_REPO = os.environ["GH_REPO"]
CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
CF_API_TOKEN = os.environ["CF_API_TOKEN"]
SPACE_URL = os.environ.get("SPACE_URL", "")

COOKIES_FILE = "/home/user/app/cookies.json"

# --- 1. MEMORIA PERSISTENTE EN GITHUB ---
def cargar_cookies_desde_github():
    url = f"https://api.github.com/repos/{GH_REPO}/contents/cookies.json"
    headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        contenido = base64.b64decode(r.json()["content"]).decode("utf-8")
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write(contenido)

def guardar_cookies_en_github():
    if not os.path.exists(COOKIES_FILE):
        return
    url = f"https://api.github.com/repos/{GH_REPO}/contents/cookies.json"
    headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    r_get = requests.get(url, headers=headers)
    sha = r_get.json().get("sha") if r_get.status_code == 200 else None

    with open(COOKIES_FILE, "rb") as f:
        b64_content = base64.b64encode(f.read()).decode("utf-8")

    payload = {"message": "Sync cookies", "content": b64_content}
    if sha:
        payload["sha"] = sha
    requests.put(url, headers=headers, json=payload)

# --- 2. DESPLIEGUE DIRECTO EN CLOUDFLARE PAGES ---
def publicar_en_cloudflare(nombre_proyecto: str, html_bytes: bytes) -> str:
    # Limpiar nombre para cumplir reglas de subdominio de Cloudflare
    slug = re.sub(r'[^a-z0-9-]', '-', nombre_proyecto.lower()).strip('-')[:45]
    if not slug:
        slug = f"web-{int(time.time())}"

    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    base_url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/pages/projects"

    # Crear el proyecto si no existe
    requests.post(base_url, headers=headers, json={
        "name": slug,
        "production_branch": "main"
    })

    # Subir index.html mediante Direct Upload API
    file_hash = hashlib.sha256(html_bytes).hexdigest()
    manifest = {"/index.html": file_hash}

    files = {
        "manifest": (None, str(manifest).replace("'", '"'), "application/json"),
        file_hash: ("index.html", html_bytes, "text/html")
    }

    deploy_url = f"{base_url}/{slug}/deployments"
    resp = requests.post(deploy_url, headers=headers, files=files)
    data = resp.json()

    if data.get("success"):
        return data["result"].get("url", f"https://{slug}.pages.dev")
    raise Exception(f"Error Cloudflare: {data.get('errors')}")

# --- 3. ENRUTAMIENTO DE MODELOS GRATUITOS ---
def obtener_llm_web(indice: int):
    # Cadena de máxima calidad para diseño web
    if indice == 0:
        return ChatGoogleGenerativeAI(model="gemini-3.8-pro", google_api_key=GEMINI_API_KEY, temperature=0.35), "Gemini 3.8 Pro"
    elif indice == 1:
        return ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=GEMINI_API_KEY, temperature=0.35), "Gemini 2.5 Pro"
    elif indice == 2 and OPENROUTER_API_KEY:
        return ChatOpenAI(
            model="deepseek/deepseek-chat:free",
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.35
        ), "DeepSeek V3 (OpenRouter)"
    elif indice == 3:
        return ChatGoogleGenerativeAI(model="gemini-3.8-flash", google_api_key=GEMINI_API_KEY, temperature=0.35), "Gemini 3.8 Flash"
    return None, None

def obtener_llm_agente(indice: int):
    # Cadena de alto volumen y visión para navegar/correos
    modelos = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    if indice < len(modelos):
        m = modelos[indice]
        return ChatGoogleGenerativeAI(model=m, google_api_key=GEMINI_API_KEY, temperature=0.2), m
    return None, None

# --- 4. INICIALIZAR NAVEGADOR ---
cargar_cookies_desde_github()
browser = Browser(
    config=BrowserConfig(
        headless=False,
        cookies_file=COOKIES_FILE,
        extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
)

async def verificar_usuario(update: Update):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Acceso denegado.")
        return False
    return True

# --- COMANDOS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_usuario(update): return
    await update.message.reply_text(
        "🚀 *Agente Autónomo + Estudio Web Listo*\n\n"
        "• `/web nombre-proyecto | descripción` -> Crea una web de lujo y la publica directo en Cloudflare Pages.\n"
        "  _Ej: `/web taller-coruna | Taller mecánico de alta gama y diagnosis en A Coruña con precios y reservas`_\n"
        "• `/pantalla` -> Abre el control remoto táctil para resolver CAPTCHAs o logins.\n"
        "• `/guardar` -> Guarda tus sesiones abiertas en GitHub.\n"
        "• *Cualquier otro mensaje:* El navegador autónomo ejecuta tu orden (buscar en Google, responder correos, publicar en webs).",
        parse_mode="Markdown"
    )

async def cmd_pantalla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_usuario(update): return
    await update.message.reply_text(f"🖥️ *Control Táctil:*\n{SPACE_URL}/vnc.html", parse_mode="Markdown")

async def cmd_guardar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_usuario(update): return
    ctx = await browser.new_context()
    await ctx.save_cookies()
    guardar_cookies_en_github()
    await update.message.reply_text("💾 Sesiones respaldadas en GitHub.")

async def cmd_web(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_usuario(update): return
    texto = " ".join(context.args)
    if "|" not in texto:
        await update.message.reply_text(
            "⚠️ Usa el formato:\n`/web nombre-proyecto | descripción detallada`\n\n"
            "Ejemplo:\n`/web reformas-elite | Empresa de reformas integrales de lujo, estética oscura y dorada, galería de proyectos, servicios, precios orientativos y contacto`",
            parse_mode="Markdown"
        )
        return

    nombre_proj, descripcion = [x.strip() for x in texto.split("|", 1)]
    msg = await update.message.reply_text("🎨 Generando diseño web nivel agencia con Gemini 3.8 Pro...")

    prompt_agencia = (
        f"Actúa como un director de arte y desarrollador frontend senior de una agencia digital de lujo. "
        f"Crea una página web completa, ultra-profesional y lista para producción para: {descripcion}.\n\n"
        f"REGLAS ESTRICTAS DE DISEÑO Y CÓDIGO:\n"
        f"1. Usa Tailwind CSS vía CDN (<script src='https://cdn.tailwindcss.com'></script>) y Google Fonts (ej. 'Cormorant Garamond' o 'Playfair Display' para títulos + 'Plus Jakarta Sans' para textos).\n"
        f"2. Estética de alta gama: paletas sofisticadas (fondos oscuros profundos #0A0A0A con acentos cálidos/dorados, o editorial minimalista hueso/carbón), espaciado generoso, bordes sutiles (border-white/10), sombras difuminadas y transiciones hover suaves.\n"
        f"3. Copywriting persuasivo y real en español (prohibido usar Lorem Ipsum). Incluye todas las secciones pedidas (Hero impactante, Servicios detallados, Tarifas/Presupuestos transparentes, Galería/Casos de éxito, Ubicación con horario y Formulario de contacto funcional visualmente).\n"
        f"4. Usa fotografías reales de alta resolución de Unsplash mediante URLs válidas y acordes al sector.\n"
        f"5. Devuelve ÚNICAMENTE el código HTML completo empezando por <!DOCTYPE html> hasta </html>, sin bloques markdown (```) ni texto adicional. Nunca abrevies el código."
    )

    html_codigo = None
    modelo_usado = ""

    for i in range(4):
        llm_web, nombre_modelo = obtener_llm_web(i)
        if not llm_web:
            continue
        try:
            await msg.edit_text(f"🎨 Diseñando con *{nombre_modelo}*...", parse_mode="Markdown")
            resp = await llm_web.ainvoke(prompt_agencia)
            html_codigo = resp.content.replace("```html", "").replace("```", "").strip()
            modelo_usado = nombre_modelo
            break
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                continue
            await msg.edit_text(f"❌ Error generando código: `{str(e)[:250]}`", parse_mode="Markdown")
            return

    if not html_codigo:
        await msg.edit_text("❌ Cuotas diarias agotadas en todos los modelos de diseño.")
        return

    await msg.edit_text(f"☁️ Web creada con *{modelo_usado}*. Subiendo a Cloudflare Pages...", parse_mode="Markdown")

    try:
        url_publicada = publicar_en_cloudflare(nombre_proj, html_codigo.encode("utf-8"))
        ruta_local = "/home/user/app/ultima_web.html"
        with open(ruta_local, "w", encoding="utf-8") as f:
            f.write(html_codigo)

        await msg.edit_text(
            f"✅ *¡Web publicada en Cloudflare!*\n\n"
            f"🌐 *Enlace activo:* {url_publicada}\n"
            f"🧠 *Modelo:* {modelo_usado}",
            parse_mode="Markdown"
        )
        await update.message.reply_document(document=open(ruta_local, "rb"), filename=f"{nombre_proj}.html")
    except Exception as e:
        await msg.edit_text(f"⚠️ Código generado, pero falló la subida a Cloudflare:\n`{str(e)[:300]}`", parse_mode="Markdown")

async def ejecutar_tarea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_usuario(update): return
    orden = update.message.text
    msg = await update.message.reply_text(f"⏳ Navegando con Gemini 3.8 Flash...\nPantalla táctil: {SPACE_URL}/vnc.html")

    for i in range(2):
        llm_ag, nombre_m = obtener_llm_agente(i)
        try:
            agent = Agent(task=orden, llm=llm_ag, browser=browser, max_actions_per_step=4)
            resultado = await agent.run(max_steps=25)
            guardar_cookies_en_github()
            final = resultado.final_result() or "Tarea completada."
            await msg.edit_text(f"✅ *Listo ({nombre_m}):*\n{final}", parse_mode="Markdown")
            return
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                await msg.edit_text(f"⚠️ Cuota de `{nombre_m}` llena, cambiando a respaldo...", parse_mode="Markdown")
                continue
            await msg.edit_text(f"⚠️ *Atasco o bloqueo:*\n`{str(e)[:280]}`\n\nToma el mando en:\n{SPACE_URL}/vnc.html", parse_mode="Markdown")
            return

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pantalla", cmd_pantalla))
    app.add_handler(CommandHandler("guardar", cmd_guardar))
    app.add_handler(CommandHandler("web", cmd_web))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ejecutar_tarea))
    app.run_polling()
