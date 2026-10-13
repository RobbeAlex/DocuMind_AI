# 🤖 DocuMind AI

![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Version 2.0](https://img.shields.io/badge/version-2.0-success.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)

Un sistema avanzado de **Retrieval-Augmented Generation (RAG)** diseñado para procesar, vectorizar y consultar documentos de manera inteligente. Utilizando la potencia de **Google Gemini** y **FastAPI**, esta solución permite a los usuarios hacer preguntas en lenguaje natural sobre sus propios documentos (`PDF`, `DOCX`, `DOC` y `TXT`) a través de una interfaz visual intuitiva desarrollada con **Streamlit**, con soporte para filtrado por documento, citas por archivo/página y gestión completa de la base de conocimiento.

> 📘 **¿Buscas especificaciones de bajo nivel?** Consulta la [Documentación Técnica Completa (DOCUMENTACION_TECNICA.md)](DOCUMENTACION_TECNICA.md).

---

## 📊 Arquitectura del Sistema

El proyecto cuenta con una arquitectura moderna y desacoplada, separando claramente la interfaz de usuario del motor de inteligencia artificial.

```mermaid
flowchart TD
    Inicio(["Inicio"])

    subgraph Cliente["Interfaz de Usuario"]
        UI["ui.py (Streamlit)<br/>Gestión de archivos y consultas"]
    end

    subgraph Configuracion["Configuración"]
        Config[/core/config.py<br/>Define API key y modelos/]
        Settings{{"Settings<br/>Carga variables de entorno (.env)"}}
        Config --> Settings
    end

    subgraph API["API Principal (FastAPI v2.0)"]
        Main(["main.py<br/>Endpoints y ciclo de vida (lifespan)"])
        Peticion[/schemas/requests.py<br/>PeticionConsulta: pregunta + documento/]
    end

    subgraph MotorRAG["Motor RAG (services/rag.py)"]
        Rag[["RagEngine (rag_engine)<br/>Coordina ingesta, catálogo y consultas"]]
        Cargar{"¿Existe índice FAISS?"}
        Reemplazar{"¿reemplazar == True?"}
        Limpiar["limpiar_base_datos()<br/>Borra memoria y faiss_index/"]
        Tipo{"¿Qué tipo de archivo?"}
        PDF["PyPDFLoader<br/>Lee PDF y páginas"]
        DOCX["Docx2txtLoader<br/>Lee DOC/DOCX"]
        Texto["TextLoader<br/>Lee TXT (UTF-8)"]
        Fragmentar["RecursiveCharacterTextSplitter<br/>Fragmenta (1000 chars / 200 overlap)"]
        Embeddings["HuggingFaceEmbeddings<br/>all-MiniLM-L6-v2"]
        Indice[("FAISS + documentos.json<br/>Base de datos vectorial persistente")]
        Recuperar["Búsqueda MMR (k=4)<br/>Con filtro opcional por documento"]
        Prompt["ChatPromptTemplate<br/>Contexto citado + reglas estrictas"]
        LLM["Google Generative AI<br/>Genera respuesta fundamentada"]
    end

    Respuesta[/Respuesta JSON<br/>Pregunta, respuesta, fuentes y contexto/]
    ListaDocs[/Respuesta JSON<br/>Catálogo de documentos/]
    Error(["Error HTTP (400 / 500)"])

    Inicio --> UI
    UI -->|HTTP REST| Main
    Settings --> Rag
    Main -->|Startup lifespan| Cargar
    Cargar -->|Sí| Indice
    Cargar -->|No| Rag

    Main -->|GET /documentos| Rag
    Rag --> ListaDocs

    Main -->|POST /limpiar| Limpiar
    Limpiar --> Indice

    Main -->|POST /ingestar| Reemplazar
    Reemplazar -->|Sí| Limpiar
    Reemplazar -->|No| Rag
    Limpiar --> Rag
    Rag --> Tipo
    Tipo -->|PDF| PDF
    Tipo -->|DOC o DOCX| DOCX
    Tipo -->|Otro formato| Texto

    PDF --> Fragmentar
    DOCX --> Fragmentar
    Texto --> Fragmentar
    Fragmentar --> Embeddings
    Embeddings --> Indice
    Indice -->|Guardar en disco| Rag

    Main -->|POST /consultar| Peticion
    Peticion --> Rag
    Rag -->|Verifica API key e índice| Cargar
    Cargar -->|Índice disponible| Recuperar
    Recuperar --> Prompt
    Prompt -->|Usa MODEL_NAME| LLM
    LLM --> Respuesta

    Rag -->|Sin API key o índice vacío| Error

    classDef inicio fill:#F8D7DA,stroke:#B85C70,color:#4A2630
    classDef archivo fill:#DDEBF7,stroke:#6B9AC4,color:#1F3A50
    classDef proceso fill:#E2F0D9,stroke:#82A66B,color:#29401F
    classDef decision fill:#FFF2CC,stroke:#C9A227,color:#554500
    classDef datos fill:#EADCF8,stroke:#9875B8,color:#38264D
    classDef salida fill:#FCE4D6,stroke:#C9825B,color:#542D1E
    classDef error fill:#F4CCCC,stroke:#B85450,color:#4A1715

    class Inicio inicio
    class UI,Config,Main,Peticion archivo
    class Settings,Rag,Limpiar,PDF,DOCX,Texto,Fragmentar,Embeddings,Recuperar,Prompt,LLM proceso
    class Cargar,Reemplazar,Tipo decision
    class Indice datos
    class Respuesta,ListaDocs salida
    class Error error
```

### Flujo de Trabajo (Ingesta, Gestión y Consulta)

El siguiente diagrama de secuencia ilustra cómo interactúan los componentes internamente al gestionar documentos y realizar consultas:

```mermaid
sequenceDiagram
    actor Usuario
    participant Streamlit
    participant FastAPI
    participant VectorDB as FAISS (faiss_index/)
    participant Gemini as Google LLM

    %% Sincronización de catálogo
    Streamlit->>FastAPI: GET /documentos
    FastAPI-->>Streamlit: Lista de documentos disponibles

    %% Flujo de Ingesta
    rect rgb(230, 240, 255)
        Note right of Usuario: Proceso de Ingesta de Documentos
        Usuario->>Streamlit: Sube archivo (PDF/DOCX/TXT) + opción "reemplazar"
        Streamlit->>FastAPI: POST /ingestar (archivo, reemplazar)
        opt Si reemplazar == True
            FastAPI->>VectorDB: Limpia índice previo
        end
        FastAPI->>FastAPI: Extrae texto, asigna metadata y divide en fragmentos (1000/200)
        FastAPI->>VectorDB: Genera Embeddings y guarda índice + documentos.json
        VectorDB-->>FastAPI: OK (Persistido en disco)
        FastAPI-->>Streamlit: "Documento procesado exitosamente" + lista actualizada
    end

    %% Flujo de Consulta
    rect rgb(240, 255, 230)
        Note right of Usuario: Proceso de Consulta (RAG con MMR)
        Usuario->>Streamlit: Selecciona documento (o Todos) y hace una pregunta
        Streamlit->>FastAPI: POST /consultar {pregunta, documento}
        FastAPI->>VectorDB: Búsqueda MMR (k=4) con filtro opcional de metadata
        VectorDB-->>FastAPI: Devuelve fragmentos relevantes con fuente y página
        FastAPI->>Gemini: Prompt estricto con (Contexto citado + Pregunta)
        Gemini-->>FastAPI: Genera respuesta fundamentada
        FastAPI-->>Streamlit: Respuesta limpia + Fuentes + Contexto extraído
        Streamlit-->>Usuario: Muestra respuesta, fuentes y fragmentos utilizados
    end
```

---

## ✨ Ventajas y Fortalezas del Proyecto

- **Arquitectura Modular y Escalable**: Separación clara de responsabilidades entre rutas de la API (`main.py`), lógica del motor RAG (`services/rag.py`), validación de esquemas (`schemas/requests.py`) y configuración (`core/config.py`).
- **Recuperación Semántica Avanzada (MMR)**: Emplea *Maximal Marginal Relevance* (`k=4`) para recuperar fragmentos relevantes pero diversos, evitando redundancia en el contexto entregado al LLM.
- **Aislamiento y Filtrado por Documento**: Permite consultar sobre toda la base de conocimiento o filtrar por un archivo específico, evitando mezclar información de distintos proyectos o documentos.
- **Trazabilidad y Citas de Fuentes**: Cada respuesta indica de qué archivo y página proviene la información, e incluye un panel desplegable con los fragmentos exactos utilizados.
- **Base de Datos Vectorial Persistente y Administrable**: Guarda tanto los vectores de FAISS como el catálogo de archivos (`documentos.json`) en disco local, permitiendo además reemplazar o vaciar la base de conocimiento con un clic.
- **Ciclo de Vida Moderno**: Implementa manejadores `lifespan` de FastAPI para la carga automática del índice vectorial al iniciar el servidor.

---

## 🔌 Endpoints de la API

| Método | Ruta | Descripción |
| :---: | :--- | :--- |
| `POST` | `/ingestar` | Sube y vectoriza un archivo (`PDF`, `DOCX`, `DOC`, `TXT`). Acepta el campo booleano `reemplazar` para reiniciar la base de datos antes de indexar. |
| `POST` | `/consultar` | Recibe `{"pregunta": "...", "documento": "..."}` y devuelve la respuesta generada, las fuentes consultadas y el contexto utilizado. |
| `GET` | `/documentos` | Retorna la lista de documentos actualmente indexados en la base de conocimiento. |
| `POST` | `/limpiar` | Elimina todos los documentos indexados y reinicia la base de datos vectorial en memoria y en disco. |

---

## 📁 Estructura del Proyecto

```text
.
├── core/
│   └── config.py                # Centralización y validación de variables de entorno
├── schemas/
│   └── requests.py              # Modelos de Pydantic para el tipado estricto
├── services/
│   └── rag.py                   # Lógica core de IA: LangChain, FAISS, MMR y Gemini
├── flowchart/
│   └── flowchart.mmd            # Diagrama de flujo de interacción entre los archivos
├── faiss_index/                 # Persistencia local de FAISS y catálogo documentos.json
├── main.py                      # Entrypoint de la API (FastAPI v2.0)
├── ui.py                        # Interfaz de usuario interactiva (Streamlit)
├── Dockerfile                   # Definición de imagen Docker para API y UI
├── docker-compose.yml           # Orquestación multicontenedor con volumen persistente
├── requirements.txt             # Dependencias estrictas del proyecto
├── DOCUMENTACION_TECNICA.md     # Documentación técnica detallada de arquitectura y API
├── .env.example                 # Plantilla de variables de entorno
├── .dockerignore                # Reglas de exclusión para contexto de Docker
├── .gitignore                   # Reglas de exclusión para Git
└── README.md                    # Documentación principal
```

## 🛠️ Instalación y Requisitos

1. Asegúrate de tener **Python >= 3.9** instalado.
2. Clona este repositorio y navega a la carpeta del proyecto.
3. Crea y activa un entorno virtual (recomendado):

   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/Mac:
   source .venv/bin/activate
   ```

4. Instala las dependencias necesarias:

   ```bash
   pip install -r requirements.txt
   ```

5. **Configura tus credenciales**:
   - Haz una copia del archivo `.env.example` y renómbralo a `.env`
   - Inserta tu API Key de Google Generative AI en el archivo:

     ```env
     GOOGLE_API_KEY=tu_api_key_aqui
     ```

## ▶️ Uso y Ejecución

El proyecto está diseñado para ejecutar el Backend y el Frontend de manera independiente. Necesitarás abrir dos terminales.

### 1. Levantar la API (Backend)

En tu primera terminal, levanta el motor principal:

```bash
uvicorn main:app --reload
```

*La API estará disponible en `http://localhost:8000`. Puedes consultar la documentación interactiva (Swagger) en `http://localhost:8000/docs`.*

### 2. Levantar la Interfaz Gráfica (Frontend)

En tu segunda terminal (con el entorno virtual activado), ejecuta:

```bash
streamlit run ui.py
```

*Se abrirá automáticamente en tu navegador web (`http://localhost:8501`). Desde ahí podrás subir tus documentos, gestionar la base de conocimiento y comenzar a hacer preguntas a la IA.*

---

## 🐳 Despliegue con Docker y Docker Compose

También puedes ejecutar todo el sistema (Backend + Frontend + Base de Datos Vectorial) empaquetado en contenedores Docker de forma automática.

### 1. Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y en ejecución.
- Archivo `.env` configurado con tu `GOOGLE_API_KEY`.

### 2. Levantar los Contenedores

Ejecuta en la raíz del proyecto:

```bash
docker compose up --build
```

*(o en segundo plano con `docker compose up --build -d`)*

### 3. Acceso a las Aplicaciones

- **Frontend (Streamlit)**: [http://localhost:8501](http://localhost:8501)
- **Backend (FastAPI)**: [http://localhost:8000](http://localhost:8000)
- **Documentación Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Detener los Contenedores

```bash
docker compose down
```

> **Nota de persistencia:** Los documentos y la base de datos vectorial se sincronizan automáticamente en la carpeta local `./faiss_index` mediante volúmenes, por lo que tus índices permanecen guardados incluso si apagas los contenedores.

## ⚙️ Stack Tecnológico

- **Backend**: FastAPI, Uvicorn, Pydantic (`pydantic-settings`)

- **Frontend**: Streamlit

- **Contenedores**: Docker, Docker Compose

- **IA y NLP**: LangChain, HuggingFace (`sentence-transformers/all-MiniLM-L6-v2`), Google Generative AI (`gemini-3.8-flash`)

- **Base de Datos Vectorial**: FAISS (`faiss-cpu`)

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
