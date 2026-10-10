# 🤖 DocuMind AI

![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)

Un sistema avanzado de **Retrieval-Augmented Generation (RAG)** diseñado para procesar, vectorizar y consultar documentos de manera inteligente. Utilizando la potencia de **Google Gemini** y **FastAPI**, esta solución permite a los usuarios hacer preguntas en lenguaje natural sobre sus propios documentos (PDF, Word DOCX/DOC y TXT) a través de una interfaz visual intuitiva desarrollada con **Streamlit**.

---

## 📊 Arquitectura del Sistema

El proyecto cuenta con una arquitectura moderna y desacoplada, separando claramente la interfaz de usuario del motor de inteligencia artificial.

```mermaid
flowchart TD
    Inicio(["Inicio"])

    subgraph Configuracion["Configuración"]
        Config[/config.py<br/>Define API key y modelos/]
        Settings{{"Settings<br/>Carga variables de entorno"}}
        Config --> Settings
    end

    subgraph API["API principal"]
        Main(["main.py<br/>Crea FastAPI y define endpoints"])
        Peticion[/schemas/requests.py<br/>Valida la pregunta recibida/]
    end

    subgraph MotorRAG["Motor RAG"]
        Rag[["services/rag.py<br/>Coordina ingesta y consultas"]]
        Cargar{"¿Existe índice FAISS?"}
        Tipo{"¿Qué tipo de archivo?"}
        PDF["PyPDFLoader<br/>Lee PDF"]
        DOCX["Docx2txtLoader<br/>Lee DOC/DOCX"]
        Texto["TextLoader<br/>Lee texto"]
        Fragmentar["Divide el documento<br/>en fragmentos"]
        Embeddings["HuggingFaceEmbeddings<br/>Convierte texto en vectores"]
        Indice[("FAISS<br/>Base de datos vectorial")]
        Recuperar["Recupera los 3 fragmentos<br/>más relevantes"]
        Prompt["Construye el prompt<br/>con el contexto"]
        LLM["Google Generative AI<br/>Genera la respuesta"]
    end

    Respuesta[/Respuesta JSON<br/>Pregunta, contexto y respuesta/]
    Error(["Error HTTP"])

    Inicio --> Main
    Settings --> Rag
    Main -->|Startup| Cargar
    Cargar -->|Sí| Indice
    Cargar -->|No| Rag

    Main -->|POST /ingestar| Rag
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
    Rag -->|Verifica configuración| Cargar
    Cargar -->|Índice disponible| Recuperar
    Recuperar --> Prompt
    Prompt -->|Usa MODEL_NAME| LLM
    LLM --> Respuesta

    Rag -->|Sin API key o índice| Error

    classDef inicio fill:#F8D7DA,stroke:#B85C70,color:#4A2630
    classDef archivo fill:#DDEBF7,stroke:#6B9AC4,color:#1F3A50
    classDef proceso fill:#E2F0D9,stroke:#82A66B,color:#29401F
    classDef decision fill:#FFF2CC,stroke:#C9A227,color:#554500
    classDef datos fill:#EADCF8,stroke:#9875B8,color:#38264D
    classDef salida fill:#FCE4D6,stroke:#C9825B,color:#542D1E
    classDef error fill:#F4CCCC,stroke:#B85450,color:#4A1715

    class Inicio inicio
    class Config,Main,Peticion archivo
    class Settings,Rag,PDF,DOCX,Texto,Fragmentar,Embeddings,Recuperar,Prompt,LLM proceso
    class Cargar,Tipo decision
    class Indice datos
    class Respuesta salida
    class Error error
```

### Flujo de Trabajo (Ingesta y Consulta)

El siguiente diagrama de secuencia ilustra cómo interactúan los componentes internamente cuando subes un documento frente a cuando realizas una consulta:

```mermaid
sequenceDiagram
    actor Usuario
    participant Streamlit
    participant FastAPI
    participant VectorDB as FAISS
    participant Gemini as Google LLM

    %% Flujo de Ingesta
    rect rgb(230, 240, 255)
        Note right of Usuario: Proceso de Ingesta de Documentos
        Usuario->>Streamlit: Sube archivo (PDF/DOCX/TXT)
        Streamlit->>FastAPI: POST /ingestar
        FastAPI->>FastAPI: Extrae texto y divide en fragmentos (Chunks)
        FastAPI->>VectorDB: Genera Embeddings y guarda fragmentos
        VectorDB-->>FastAPI: OK (Persistido en disco)
        FastAPI-->>Streamlit: "Documento procesado exitosamente"
    end

    %% Flujo de Consulta
    rect rgb(240, 255, 230)
        Note right of Usuario: Proceso de Consulta (RAG)
        Usuario->>Streamlit: Hace una pregunta
        Streamlit->>FastAPI: POST /consultar {pregunta}
        FastAPI->>VectorDB: Búsqueda de similitud (Top-K fragmentos)
        VectorDB-->>FastAPI: Devuelve contexto relevante
        FastAPI->>Gemini: Prompt con (Contexto + Pregunta)
        Gemini-->>FastAPI: Genera respuesta informada
        FastAPI-->>Streamlit: Respuesta limpia + Contexto extraído
        Streamlit-->>Usuario: Muestra la respuesta en pantalla
    end
```

---

## ✨ Ventajas y Fortalezas del Proyecto

- **Arquitectura Modular y Escalable**: Código limpio y organizado utilizando principios de diseño de software. Separación clara de responsabilidades entre las rutas de la API, la lógica del negocio (IA) y los modelos de datos.
- **Base de Datos Vectorial Persistente**: Utiliza FAISS para crear representaciones vectoriales (Embeddings) de los documentos. El conocimiento se guarda en disco localmente, garantizando que no se pierdan los datos tras reiniciar el servidor.
- **Interfaz Gráfica Intuitiva (UI)**: Desacopla la lógica del backend ofreciendo un frontend moderno con Streamlit. Los usuarios finales no necesitan usar comandos cURL o Postman; pueden arrastrar sus PDFs y chatear de inmediato.
- **Seguridad y Buenas Prácticas**: Manejo seguro de credenciales (API Keys) a través de variables de entorno y validación estricta de los datos de entrada y salida mediante Pydantic.
- **Ciclo de Vida Moderno**: Implementa manejadores de estado modernos (`lifespan`) de FastAPI para una correcta inicialización y limpieza de recursos (como la carga en memoria de los modelos de IA).

## 📁 Estructura del Proyecto

```text
.
├── core/
│   └── config.py          # Centralización y validación de variables de entorno
├── schemas/
│   └── requests.py        # Modelos de Pydantic para el tipado estricto
├── services/
│   └── rag.py             # Lógica core de IA: LangChain, FAISS y Gemini
├── flowchart/
│   └── flowchart.mmd      # Diagrama de flujo de interacción entre los archivos
├── main.py                # Entrypoint de la API (FastAPI)
├── ui.py                  # Interfaz de usuario (Streamlit)
├── requirements.txt       # Dependencias estrictas del proyecto
├── .env.example           # Plantilla de variables de entorno
├── .gitignore             # Reglas de exclusión para Git
└── README.md              # Documentación principal
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
*Se abrirá automáticamente en tu navegador web. Desde ahí podrás subir tus documentos PDF/TXT y comenzar a hacer preguntas a la IA.*

## ⚙️ Stack Tecnológico
* **Backend**: FastAPI, Uvicorn, Pydantic
* **Frontend**: Streamlit
* **IA y NLP**: LangChain, HuggingFace (Embeddings), Google Generative AI (Gemini)
* **Base de Datos Vectorial**: FAISS

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
