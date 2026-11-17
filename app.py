import os
import streamlit as st
from google import genai
from google.genai import types

# Configuración de la página
st.set_page_config(
    page_title="Centro de Control de Agentes",
    page_icon="🧠",
    layout="centered"
)

# Estilo visual moderno y limpio
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stTextInput textarea { color: #ffffff; }
    </style>
""", unsafe_allow_html=True)

st.title("🧠 Centro de Control y Agentes IA")

# Barra lateral de configuración
st.sidebar.header("Configuración")
modelo_activo = st.sidebar.selectbox(
    "Modelo activo",
    ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.8-flash"]
)

modo_operacion = st.sidebar.radio(
    "Modo de Operación",
    ["Chat Ejecutivo / Estrategia", "Agente Web Autónomo (Browser-Use)"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📁 Adjuntar Archivos")
archivo_cargado = st.sidebar.file_uploader(
    "Sube una imagen, PDF o documento",
    type=["png", "jpg", "jpeg", "pdf", "txt", "csv"]
)

# Inicializar cliente de Gemini usando la API Key del entorno
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("⚠️ No se ha detectado la variable GEMINI_API_KEY en el entorno de Codespaces.")
    st.info("Ejecuta en tu terminal: export GEMINI_API_KEY='tu_clave' y reinicia Streamlit.")
else:
    client = genai.Client(api_key=api_key)

# Historial de chat en sesión
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar mensajes anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrada de usuario en el chat
if prompt := st.chat_input("¿Qué tarea quieres ejecutar o qué duda tienes?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if archivo_cargado:
            st.caption(f"📎 Archivo adjunto: {archivo_cargado.name}")

    with st.chat_message("assistant"):
        with st.spinner("Procesando solicitud..."):
            try:
                # Preparar contenido multimedia si se subió un archivo
                contents = [prompt]
                
                if archivo_cargado:
                    bytes_data = archivo_cargado.getvalue()
                    # Subir archivo al cliente de Gemini
                    uploaded_file = client.files.upload(
                        file=bytes_data,
                        config=types.UploadFileConfig(mime_type=archivo_cargado.type)
                    )
                    contents.append(uploaded_file)

                if modo_operacion == "Chat Ejecutivo / Estrategia":
                    # Llamada directa a la API de Gemini con soporte multimodal
                    response = client.models.generate_content(
                        model=modelo_activo,
                        contents=contents
                    )
                    respuesta_texto = response.text
                else:
                    # Modo Agente Autónomo (Placeholder listo para integrar browser-use)
                    respuesta_texto = (
                        f"🤖 **[Modo Agente Web Autónomo]**\n\n"
                        f"He recibido tu tarea: *'{prompt}'*\n"
                        f"El entorno de navegador autónomo se activará para ejecutar la automatización usando tus `cookies.json`."
                    )

                st.markdown(respuesta_texto)
                st.session_state.messages.append({"role": "assistant", "content": respuesta_texto})

            except Exception as e:
                error_msg = f"❌ Error al procesar la solicitud: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
