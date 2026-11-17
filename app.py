import os
import json
import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Browser, Agent

st.set_page_config(page_title="Centro de Control de IA", page_icon="🤖", layout="wide")

# Configurar claves desde las Secrets de GitHub Codespaces
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

st.title("🧠 Centro de Control y Agentes de IA")
st.sidebar.header("Configuración")

# Selector de modelo
modelo_seleccionado = st.sidebar.selectbox(
    "Modelo activo",
    ["gemini-3.8-flash", "gemini-pro"]
)

modo_trabajo = st.sidebar.radio(
    "Modo de Operación",
    ["Chat Ejecutivo / Estrategia", "Agente Web Autónomo (Browser-Use)"]
)

# Historial de chat visual en Streamlit
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

for msg in st.session_state.mensajes:
    with st.chat_message(msg["rol"]):
        st.markdown(msg["texto"])

prompt_usuario = st.chat_input("¿Qué tarea quieres ejecutar o qué duda tienes?")

if prompt_usuario:
    st.session_state.mensajes.append({"rol": "user", "texto": prompt_usuario})
    with st.chat_message("user"):
        st.markdown(prompt_usuario)

    with st.chat_message("assistant"):
        with st.spinner("Ejecutando proceso..."):
            try:
                llm = ChatGoogleGenerativeAI(model=modelo_seleccionado, google_api_key=GEMINI_API_KEY)
                
                if modo_trabajo == "Chat Ejecutivo / Estrategia":
                    respuesta = llm.invoke(prompt_usuario).content
                    st.markdown(respuesta)
                    st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta})
                
                else:
                    st.info("🌐 Iniciando navegador headless para tarea web...")
                    # Modo headless puro para evitar bloqueos en entornos de servidor
                    browser = Browser(headless=True, extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"])
                    agent = Agent(task=prompt_usuario, browser=browser, llm=llm)
                    
                    # Ejecutar agente
                    import asyncio
                    resultado = asyncio.run(agent.run())
                    
                    st.markdown(f"**Resultado de la tarea web:**\n\n{str(resultado)}")
                    st.session_state.mensajes.append({"rol": "assistant", "texto": str(resultado)})
                    
            except Exception as e:
                error_msg = f"❌ Error en la ejecución: {e}"
                st.error(error_msg)
                st.session_state.mensajes.append({"rol": "assistant", "texto": error_msg})
