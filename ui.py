import os
import streamlit as st
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="DocuMind AI", page_icon="🤖", layout="centered")

def obtener_lista_documentos():
    try:
        response = requests.get(f"{API_URL}/documentos", timeout=5)
        if response.status_code == 200:
            return response.json().get("documentos", [])
    except Exception:
        pass
    return []

documentos_disponibles = obtener_lista_documentos()

st.title("🤖 DocuMind AI")
st.markdown("Sube tus documentos y haz preguntas sobre ellos utilizando inteligencia artificial.")

# Sidebar para la ingesta y gestión de documentos
with st.sidebar:
    st.header("1. Ingesta de documentos")
    uploaded_file = st.file_uploader("Sube un archivo (PDF, TXT, DOCX)", type=["pdf", "txt", "docx", "doc"])
    
    modo_reemplazar = st.checkbox(
        "Reemplazar documentos previos", 
        value=False, 
        help="Si se activa, borra la base de datos previa para trabajar exclusivamente con este nuevo archivo sin mezclar información."
    )
    
    if st.button("Procesar documento", type="primary"):
        if uploaded_file is not None:
            with st.spinner("Procesando y guardando en base de datos..."):
                files = {"archivo": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"reemplazar": str(modo_reemplazar).lower()}
                try:
                    response = requests.post(f"{API_URL}/ingestar", files=files, data=data)
                    if response.status_code == 200:
                        st.success(response.json().get("mensaje", "Documento procesado exitosamente."))
                        st.rerun()
                    else:
                        st.error(f"Error: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("No se pudo conectar a la API. Asegúrate de que FastAPI esté corriendo (uvicorn main:app --reload).")
        else:
            st.warning("Por favor, sube un archivo primero.")

    st.divider()

    st.header("Base de conocimiento")
    if documentos_disponibles:
        st.caption(f"Archivos disponibles ({len(documentos_disponibles)}):")
        for doc in documentos_disponibles:
            st.markdown(f"- 📄 `{doc}`")
    else:
        st.caption("No hay documentos en la base de datos.")

    if st.button("🗑️ Vaciar base de datos", help="Elimina todos los documentos indexados para reiniciar desde cero"):
        try:
            res = requests.post(f"{API_URL}/limpiar")
            if res.status_code == 200:
                st.success("Base de conocimiento vaciada con éxito.")
                st.rerun()
            else:
                st.error("No se pudo limpiar la base de datos.")
        except requests.exceptions.ConnectionError:
            st.error("No se pudo conectar a la API.")

# Área principal para consultas
st.header("2. Consultas")

if documentos_disponibles:
    opciones = ["Todos los documentos"] + documentos_disponibles
    doc_seleccionado = st.selectbox(
        "Consultar en:", 
        options=opciones, 
        index=0,
        help="Selecciona un archivo específico para evitar que se mezcle información de otros documentos."
    )
    filtro_doc = None if doc_seleccionado == "Todos los documentos" else doc_seleccionado
else:
    filtro_doc = None

pregunta = st.text_input("Haz una pregunta sobre los documentos ingestados:")

if st.button("Consultar"):
    if pregunta.strip():
        with st.spinner("Buscando respuesta..."):
            try:
                payload = {"pregunta": pregunta}
                if filtro_doc:
                    payload["documento"] = filtro_doc

                response = requests.post(f"{API_URL}/consultar", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    st.markdown("### Respuesta:")
                    
                    respuesta_cruda = data["respuesta"]

                    def extraer_solo_texto(valor):
                        import json
                        import ast

                        if isinstance(valor, str):
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
                            candidatos = [str(v) for k, v in valor.items() if k not in ("type", "extras", "signature")]
                            return "\n\n".join(candidatos) if candidatos else str(valor)
                        return str(valor)

                    texto_final = extraer_solo_texto(respuesta_cruda)
                    st.markdown(texto_final)

                    fuentes = data.get("fuentes", [])
                    if fuentes:
                        st.caption(f"**Fuentes consultadas:** {', '.join([f'`{f}`' for f in fuentes])}")
                    
                    with st.expander("Ver fragmentos de contexto utilizados por la IA"):
                        st.text(data["contexto_utilizado"])
                else:
                    st.error(f"Error: {response.json().get('detail', 'Error desconocido')}")
            except requests.exceptions.ConnectionError:
                st.error("No se pudo conectar a la API. Asegúrate de que FastAPI esté corriendo (uvicorn main:app --reload).")
    else:
        st.warning("Por favor, escribe una pregunta.")

