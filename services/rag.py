import os
import shutil
import json
from typing import Optional, List
from fastapi import UploadFile, HTTPException
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from core.config import settings

class RagEngine:
    def __init__(self):
        self.vector_store = None
        self.documentos_cargados: List[str] = []
        # Inicializa embeddings
        self.embeddings_modelo = HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL)
        
        # Inicializa el LLM. Si no hay GOOGLE_API_KEY, fallará aquí, pero FastAPI capturará el error si se usa en endpoint
        if settings.GOOGLE_API_KEY:
            self.llm_modelo = ChatGoogleGenerativeAI(
                model=settings.MODEL_NAME, 
                temperature=0.2, 
                google_api_key=settings.GOOGLE_API_KEY
            )
        else:
            self.llm_modelo = None

    def load_vector_store(self, store_path="faiss_index"):
        """Carga el vector store si existe en disco para persistencia y recupera la lista de documentos."""
        if os.path.exists(store_path) and os.path.isdir(store_path):
            try:
                self.vector_store = FAISS.load_local(
                    store_path, 
                    self.embeddings_modelo, 
                    allow_dangerous_deserialization=True
                )
                print(f"Base de datos vectorial cargada desde {store_path}")

                # Cargar registro de documentos ingestados
                docs_file = os.path.join(store_path, "documentos.json")
                if os.path.exists(docs_file):
                    try:
                        with open(docs_file, "r", encoding="utf-8") as f:
                            self.documentos_cargados = json.load(f)
                    except Exception as err:
                        print(f"Error al leer documentos.json: {err}")
                else:
                    # Si no existe el json, extraer nombres de la metadata de los documentos en memoria
                    encontrados = set()
                    if hasattr(self.vector_store, "docstore") and hasattr(self.vector_store.docstore, "_dict"):
                        for doc in self.vector_store.docstore._dict.values():
                            if hasattr(doc, "metadata"):
                                nom = doc.metadata.get("documento")
                                if not nom and "source" in doc.metadata:
                                    nom = os.path.basename(doc.metadata["source"]).replace("temp_", "")
                                if nom:
                                    encontrados.add(nom)
                    self.documentos_cargados = sorted(list(encontrados))
            except Exception as e:
                print(f"No se pudo cargar la base de datos local: {e}")

    def save_vector_store(self, store_path="faiss_index"):
        """Guarda el vector store y la lista de documentos en disco."""
        if self.vector_store:
            self.vector_store.save_local(store_path)
            try:
                docs_file = os.path.join(store_path, "documentos.json")
                with open(docs_file, "w", encoding="utf-8") as f:
                    json.dump(self.documentos_cargados, f, ensure_ascii=False, indent=2)
            except Exception as err:
                print(f"Error al guardar documentos.json: {err}")

    def limpiar_base_datos(self, store_path="faiss_index"):
        """Elimina todos los documentos y reinicia el índice vectorial tanto en memoria como en disco."""
        self.vector_store = None
        self.documentos_cargados = []
        if os.path.exists(store_path):
            try:
                shutil.rmtree(store_path, ignore_errors=True)
            except Exception as err:
                print(f"Error al borrar {store_path}: {err}")
        return {"mensaje": "Base de conocimiento limpiada exitosamente. El índice está vacío."}

    def obtener_documentos(self) -> List[str]:
        """Devuelve los nombres de los documentos actualmente almacenados."""
        return self.documentos_cargados

    def ingestar_documento(self, archivo: UploadFile, reemplazar: bool = False):
        ruta_temporal = f"temp_{archivo.filename}"
        try:
            if reemplazar:
                self.limpiar_base_datos()

            with open(ruta_temporal, "wb") as buffer:
                shutil.copyfileobj(archivo.file, buffer)

            # Cargar el documento dependiendo de su extensión
            if archivo.filename.lower().endswith(".pdf"):
                cargador = PyPDFLoader(ruta_temporal)
            elif archivo.filename.lower().endswith((".docx", ".doc")):
                cargador = Docx2txtLoader(ruta_temporal)
            else:
                cargador = TextLoader(ruta_temporal, encoding="utf-8")

            documentos = cargador.load()

            # Asignar explícitamente el nombre del documento en la metadata
            for doc in documentos:
                doc.metadata["documento"] = archivo.filename

            # Fragmentación (Chunking)
            divisor = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len
            )
            fragmentos = divisor.split_documents(documentos)

            # Asegurar metadata en cada fragmento
            for frag in fragmentos:
                frag.metadata["documento"] = archivo.filename

            # Vectorización y almacenamiento
            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(fragmentos, self.embeddings_modelo)
            else:
                self.vector_store.add_documents(fragmentos)

            if archivo.filename not in self.documentos_cargados:
                self.documentos_cargados.append(archivo.filename)

            # Guardar a disco
            self.save_vector_store()

            return {
                "mensaje": f"Documento '{archivo.filename}' procesado exitosamente. Se generaron {len(fragmentos)} fragmentos.",
                "documentos": self.documentos_cargados
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al procesar el documento: {str(e)}")

        finally:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)

    def consultar(self, pregunta: str, documento: Optional[str] = None):
        if self.llm_modelo is None:
            raise HTTPException(status_code=500, detail="El LLM no está configurado. Revisa tu GOOGLE_API_KEY.")
            
        if self.vector_store is None:
            raise HTTPException(status_code=400, detail="La base de conocimiento está vacía. Ingesta documentos primero.")

        try:
            # Definir filtro si se especificó un documento en particular
            filtro = None
            if documento and documento.strip() and documento != "Todos los documentos":
                doc_target = documento.strip()
                def filtro_fn(metadata):
                    m_doc = metadata.get("documento", "")
                    m_src = metadata.get("source", "")
                    return m_doc == doc_target or (doc_target in m_src if m_src else False)
                filtro = filtro_fn

            # Recuperar fragmentos mediante MMR con filtro opcional
            if filtro:
                documentos_recuperados = self.vector_store.max_marginal_relevance_search(
                    pregunta,
                    k=4,
                    fetch_k=15,
                    filter=filtro
                )
            else:
                documentos_recuperados = self.vector_store.max_marginal_relevance_search(
                    pregunta,
                    k=4,
                    fetch_k=10
                )

            if not documentos_recuperados:
                msg = f"No se encontró información relevante para responder la pregunta en el documento '{documento}'." if documento and documento != "Todos los documentos" else "No se encontró información relevante en los documentos consultados."
                return {
                    "pregunta": pregunta,
                    "documento_filtrado": documento,
                    "contexto_utilizado": "",
                    "respuesta": msg,
                    "fuentes": []
                }

            # Formatear el contexto con procedencia clara por fragmento (archivo y página)
            partes_contexto = []
            fuentes_utilizadas = set()
            for i, doc in enumerate(documentos_recuperados, 1):
                doc_nom = doc.metadata.get("documento") or os.path.basename(doc.metadata.get("source", "Documento")).replace("temp_", "")
                fuentes_utilizadas.add(doc_nom)
                pagina = doc.metadata.get("page")
                encabezado = f"[Fuente {i}: Documento '{doc_nom}'"
                if pagina is not None:
                    encabezado += f" | Página {pagina + 1}"
                encabezado += "]"
                partes_contexto.append(f"{encabezado}\n{doc.page_content}")

            contexto_extraido = "\n\n---\n\n".join(partes_contexto)

            plantilla_sistema = (
                "Eres un asistente analítico experto en procesamiento y consulta de documentos. "
                "Responde a la pregunta planteada basándote EXCLUSIVAMENTE en los fragmentos de contexto proporcionados.\n\n"
                "NORMAS ESTRICTAS DE RESPUESTA:\n"
                "1. Fidelidad estricta al contexto: No agregues información externa, ni inventes datos que no estén explícitamente en el contexto.\n"
                "2. Cita de fuentes: Cada fragmento incluye el archivo de origen y la página. Indica con precisión de qué documento proviene cada dato.\n"
                "3. PROHIBIDO MEZCLAR DOCUMENTOS O PROYECTOS DISTINTOS: Si los fragmentos corresponden a diferentes documentos, materias o proyectos, NUNCA los combines ni los presentes como parte de un mismo trabajo o reporte. Trata cada documento de forma independiente y separada.\n"
                "4. Enfoque: Si el usuario pregunta por un documento específico o un tema en particular, responde ÚNICAMENTE con los datos que pertenezcan a ese documento o tema.\n"
                "5. Si el contexto no contiene la respuesta, indica con honestidad: 'No dispongo de esa información en los fragmentos analizados.'\n\n"
                "Contexto:\n{context}"
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", plantilla_sistema),
                ("human", "{input}"),
            ])

            # Invocar LLM
            prompt_form = prompt.invoke({"context": contexto_extraido, "input": pregunta})
            respuesta_llm = self.llm_modelo.invoke(prompt_form)

            # Limpiar la respuesta extrayendo estrictamente el texto
            contenido = respuesta_llm.content

            def extraer_texto(c):
                if isinstance(c, str):
                    return c
                elif isinstance(c, list):
                    partes = []
                    for elemento in c:
                        if isinstance(elemento, str):
                            partes.append(elemento)
                        elif isinstance(elemento, dict):
                            if "text" in elemento:
                                partes.append(elemento["text"])
                            elif "content" in elemento:
                                partes.append(str(elemento["content"]))
                        elif hasattr(elemento, "text"):
                            partes.append(str(elemento.text))
                        elif hasattr(elemento, "content"):
                            partes.append(str(elemento.content))
                    return "\n\n".join(partes)
                elif isinstance(c, dict):
                    return c.get("text", c.get("content", str(c)))
                return str(c)

            texto_limpio = extraer_texto(contenido).strip()
            if texto_limpio.startswith("```json"):
                texto_limpio = texto_limpio.replace("```json", "").replace("```", "").strip()

            return {
                "pregunta": pregunta,
                "documento_filtrado": documento,
                "contexto_utilizado": contexto_extraido,
                "respuesta": texto_limpio,
                "fuentes": sorted(list(fuentes_utilizadas))
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error en la consulta: {str(e)}")

# Instancia global para ser usada en los endpoints
rag_engine = RagEngine()
