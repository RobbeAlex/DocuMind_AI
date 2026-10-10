from fastapi import FastAPI, UploadFile, File
from contextlib import asynccontextmanager
from schemas.requests import PeticionConsulta
from services.rag import rag_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lógica de inicio (startup)
    print("Iniciando aplicación y cargando modelos...")
    rag_engine.load_vector_store()
    yield
    # Lógica de apagado (shutdown)
    print("Apagando aplicación...")

app = FastAPI(title="DocuMind AI API", version="2.0", lifespan=lifespan)

@app.post("/ingestar")
async def ingestar_documento(archivo: UploadFile = File(...)):
    """
    Sube un documento (PDF o texto), lo fragmenta y lo almacena en la base de datos vectorial persistente.
    """
    return rag_engine.ingestar_documento(archivo)

@app.post("/consultar")
async def consultar_rag(peticion: PeticionConsulta):
    """
    Recibe una pregunta, busca el contexto relevante en el documento ingestado y genera una respuesta con el LLM.
    """
    return rag_engine.consultar(peticion.pregunta)
