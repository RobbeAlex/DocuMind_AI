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

                    def extraer_solo_texto(valor):
                        import json
                        import ast

                        if isinstance(valor, str):
                            # Si es un string, verificar si viene codificado como JSON o dict/list literal
                            valor_str = valor.strip()
                            if (valor_str.startswith("{") and valor_str.endswith("}")) or (valor_str.startswith("[") and valor_str.endswith("]")):
                                try:
                                    parsed = json.loads(valor_str)
                                    return extraer_solo_texto(parsed)
                                except (json.JSONDecodeError, TypeError):
                                    try:
                                        parsed = ast.literal_eval(valor_str)
                                        return extraer_solo_texto(parsed)
                                    except (SyntaxError, ValueError):
                                        pass
                            return valor
                        elif isinstance(valor, list):
                            partes = [extraer_solo_texto(elem) for elem in valor]
                            return "\n\n".join([p for p in partes if p])
                        elif isinstance(valor, dict):
                            if "text" in valor:
                                return extraer_solo_texto(valor["text"])
                            elif "content" in valor:
                                return extraer_solo_texto(valor["content"])
                            # Si no tiene 'text', extraer solo valores string ignorando 'type', 'extras', etc.
                            candidatos = [str(v) for k, v in valor.items() if k not in ("type", "extras", "signature")]
                            return "\n\n".join(candidatos) if candidatos else str(valor)
                        return str(valor)

                    texto_final = extraer_solo_texto(respuesta_cruda)
                    st.markdown(texto_final)
                    
                    with st.expander("Ver contexto utilizado por la IA"):
                        st.text(data["contexto_utilizado"])
                else:
                    st.error(f"Error: {response.json().get('detail', 'Error desconocido')}")
            except requests.exceptions.ConnectionError:
                st.error("No se pudo conectar a la API. Asegúrate de que FastAPI esté corriendo (uvicorn main:app --reload).")
    else:
        st.warning("Por favor, escribe una pregunta.")
