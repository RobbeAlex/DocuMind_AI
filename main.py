from fastapi import FastAPI, UploadFile, File, Form
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
async def ingestar_documento(
    archivo: UploadFile = File(...),
    reemplazar: bool = Form(False)
):
    """
    Sube un documento (PDF, DOCX o texto), lo fragmenta y lo almacena.
    Si reemplazar=True, limpia la base de datos anterior y deja solo este documento.
    """
    return rag_engine.ingestar_documento(archivo, reemplazar=reemplazar)

@app.post("/consultar")
async def consultar_rag(peticion: PeticionConsulta):
    """
    Recibe una pregunta y opcionalmente el nombre del documento específico a consultar.
    """
    return rag_engine.consultar(peticion.pregunta, documento=peticion.documento)

@app.post("/limpiar")
async def limpiar_base_conocimiento():
    """
    Elimina todos los documentos y reinicia el índice vectorial.
    """
    return rag_engine.limpiar_base_datos()

@app.get("/documentos")
async def listar_documentos():
    """
    Retorna la lista de documentos actualmente disponibles en la base de datos vectorial.
    """
    return {"documentos": rag_engine.obtener_documentos()}
