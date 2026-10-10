import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="DocuMind AI", page_icon="🤖", layout="centered")

st.title("🤖 DocuMind AI")
st.markdown("Sube tus documentos y haz preguntas sobre ellos utilizando inteligencia artificial.")

# Sidebar para la ingesta de documentos
with st.sidebar:
    st.header("1. Ingesta de Documentos")
    uploaded_file = st.file_uploader("Sube un archivo (PDF, TXT, DOCX)", type=["pdf", "txt", "docx", "doc"])
    
    if st.button("Procesar Documento"):
        if uploaded_file is not None:
            with st.spinner("Procesando y guardando en base de datos..."):
                files = {"archivo": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                try:
                    response = requests.post(f"{API_URL}/ingestar", files=files)
                    if response.status_code == 200:
                        st.success(response.json()["mensaje"])
                    else:
                        st.error(f"Error: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("No se pudo conectar a la API. Asegúrate de que FastAPI esté corriendo (uvicorn main:app --reload).")
        else:
            st.warning("Por favor, sube un archivo primero.")

# Área principal para consultas
st.header("2. Consultas")
pregunta = st.text_input("Haz una pregunta sobre los documentos ingestados:")

if st.button("Consultar"):
    if pregunta.strip():
        with st.spinner("Buscando respuesta..."):
            try:
                response = requests.post(f"{API_URL}/consultar", json={"pregunta": pregunta})
                if response.status_code == 200:
                    data = response.json()
                    st.markdown("### Respuesta:")
                    
                    respuesta_cruda = data["respuesta"]
                    texto_final = respuesta_cruda
                    
                    # Intentar extraer solo el texto si la respuesta viene en formato dict o JSON
                    import json
                    import ast
                    if isinstance(respuesta_cruda, dict):
                        texto_final = respuesta_cruda.get("text", respuesta_cruda)
                    elif isinstance(respuesta_cruda, str):
                        try:
                            # 1. Intentar como JSON estricto
                            parsed = json.loads(respuesta_cruda)
                            if isinstance(parsed, dict) and "text" in parsed:
                                texto_final = parsed["text"]
                        except json.JSONDecodeError:
                            try:
                                # 2. Intentar evaluar como diccionario de Python (si usa comillas simples)
                                parsed = ast.literal_eval(respuesta_cruda)
                                if isinstance(parsed, dict) and "text" in parsed:
                                    texto_final = parsed["text"]
                            except (SyntaxError, ValueError):
                                pass
                            
                    st.write(texto_final)
                    
                    with st.expander("Ver contexto utilizado por la IA"):
                        st.text(data["contexto_utilizado"])
                else:
                    st.error(f"Error: {response.json().get('detail', 'Error desconocido')}")
            except requests.exceptions.ConnectionError:
                st.error("No se pudo conectar a la API. Asegúrate de que FastAPI esté corriendo (uvicorn main:app --reload).")
    else:
        st.warning("Por favor, escribe una pregunta.")
