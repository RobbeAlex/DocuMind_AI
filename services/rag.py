import os
import shutil
from fastapi import UploadFile, HTTPException
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from core.config import settings

class RagEngine:
    def __init__(self):
        self.vector_store = None
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
        """Carga el vector store si existe en disco para persistencia."""
        if os.path.exists(store_path) and os.path.isdir(store_path):
            try:
                self.vector_store = FAISS.load_local(
                    store_path, 
                    self.embeddings_modelo, 
                    allow_dangerous_deserialization=True
                )
                print(f"Base de datos vectorial cargada desde {store_path}")
            except Exception as e:
                print(f"No se pudo cargar la base de datos local: {e}")

    def save_vector_store(self, store_path="faiss_index"):
        """Guarda el vector store en disco."""
        if self.vector_store:
            self.vector_store.save_local(store_path)

    def ingestar_documento(self, archivo: UploadFile):
        ruta_temporal = f"temp_{archivo.filename}"
        try:
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

            # Fragmentación (Chunking)
            divisor = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len
            )
            fragmentos = divisor.split_documents(documentos)

            # Vectorización y almacenamiento
            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(fragmentos, self.embeddings_modelo)
            else:
                self.vector_store.add_documents(fragmentos)
                
            # Guardar a disco
            self.save_vector_store()

            return {
                "mensaje": f"Documento '{archivo.filename}' procesado exitosamente. Se generaron {len(fragmentos)} fragmentos."
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al procesar el documento: {str(e)}")

        finally:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)

    def consultar(self, pregunta: str):
        if self.llm_modelo is None:
            raise HTTPException(status_code=500, detail="El LLM no está configurado. Revisa tu GOOGLE_API_KEY.")
            
        if self.vector_store is None:
            raise HTTPException(status_code=400, detail="La base de conocimiento está vacía. Ingesta documentos primero.")

        try:
            # Configurar el recuperador
            recuperador = self.vector_store.as_retriever(search_kwargs={"k": 3})

            plantilla_sistema = (
                "Eres un asistente corporativo de inteligencia artificial. "
                "Utiliza exclusivamente los siguientes fragmentos de contexto recuperado para responder a la pregunta de manera precisa. "
                "Si no sabes la respuesta basándote en el contexto, indica que no tienes esa información. "
                "\n\n"
                "Contexto:\n{context}"
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", plantilla_sistema),
                ("human", "{input}"),
            ])

            # Buscar fragmentos relevantes
            documentos_recuperados = recuperador.invoke(pregunta)
            contexto_extraido = "\n\n".join([doc.page_content for doc in documentos_recuperados])

            # Invocar LLM
            prompt_form = prompt.invoke({"context": contexto_extraido, "input": pregunta})
            respuesta_llm = self.llm_modelo.invoke(prompt_form)

            return {
                "pregunta": pregunta,
                "contexto_utilizado": contexto_extraido,
                "respuesta": respuesta_llm.content
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error en la consulta: {str(e)}")

# Instancia global para ser usada en los endpoints
rag_engine = RagEngine()
