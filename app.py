import os
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Centro de Control de Agentes",
    page_icon="🧠",
    layout="centered"
)

st.title("🧠 Centro de Control y Agentes IA")

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

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("⚠️ No se ha detectado la variable GEMINI_API_KEY en el entorno.")
else:
    client = genai.Client(api_key=api_key)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("¿Qué tarea quieres ejecutar o qué duda tienes?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if archivo_cargado:
            st.caption(f"📎 Archivo adjunto: {archivo_cargado.name}")

    with st.chat_message("assistant"):
        with st.spinner("Procesando solicitud..."):
            try:
                contents = [prompt]
                if archivo_cargado:
                    bytes_data = archivo_cargado.getvalue()
                    uploaded_file = client.files.upload(
                        file=bytes_data,
                        config=types.UploadFileConfig(mime_type=archivo_cargado.type)
                    )
                    contents.append(uploaded_file)

                if modo_operacion == "Chat Ejecutivo / Estrategia":
                    response = client.models.generate_content(
                        model=modelo_activo,
                        contents=contents
                    )
                    respuesta_texto = response.text
                else:
                    respuesta_texto = (
                        f"🤖 **[Modo Agente Web Autónomo]**\n\n"
                        f"He recibido tu tarea: *'{prompt}'*\n"
                        f"El navegador autónomo ejecutará la acción usando `cookies.json`."
                    )

                st.markdown(respuesta_texto)
                st.session_state.messages.append({"role": "assistant", "content": respuesta_texto})
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
