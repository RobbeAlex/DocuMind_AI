FROM python:3.11-slim

# Evitar prompts interactivos y buffering en consola
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar utilidades mínimas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar la caché de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Exponer puertos: 8000 para FastAPI y 8501 para Streamlit
EXPOSE 8000 8501

# Comando por defecto para la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
