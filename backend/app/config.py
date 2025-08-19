"""
app/config.py

Objetivo del documento:
-----------------------
Centralizar la configuración de embeddings, LLMs y rutas de almacenamiento.

Responsabilidades clave:
- Cargar variables desde entorno (.env).
- Definir funciones helper de rutas y configuración.
"""

import os
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("PROVIDER","ollama").lower()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","") # En caso de obtener una key openAI se debe añadir AQUI.
OPENAI_MODEL = os.getenv("OPENAI_MODEL","gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL","text-embedding-3-small")

# Ollama (Empleada en esta ocasión)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL","http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL","mistral")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL","nomic-embed-text")

# HF embeddings
USE_HF_EMBEDDINGS = os.getenv("USE_HF_EMBEDDINGS","true").lower() == "true"
HF_EMBEDDINGS_MODEL = os.getenv("HF_EMBEDDINGS_MODEL","sentence-transformers/all-MiniLM-L6-v2")

# Vector store
CHROMA_BASE_DIR = os.getenv("CHROMA_BASE_DIR","/app/data/chroma")

# Demo mode
MOCK_MODE = os.getenv("MOCK_MODE","false").lower() == "true"

def corpus_dir(corpus_id: str) -> str:
    """Devuelve la ruta en disco para un corpus.

    Objetivo:
        Resolver la carpeta de almacenamiento de Chroma.

    Entrada:
        corpus_id (str): Identificador del corpus.

    Salida:
        str: Ruta absoluta del corpus en disco.
    """
    return os.path.join(CHROMA_BASE_DIR, corpus_id)
