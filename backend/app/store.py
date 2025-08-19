"""
app/store.py

Objetivo del documento:
-----------------------
Gestiona la persistencia de embeddings en Chroma y la recuperación de bases vectoriales.

Responsabilidades clave:
- Crear corpus únicos en disco.
- Insertar o actualizar textos + metadatos.
- Retornar manejadores a colecciones Chroma.
"""
import os, uuid
from typing import List, Dict
from langchain_community.vectorstores import Chroma
from .config import (
    PROVIDER, OPENAI_EMBEDDING_MODEL, OLLAMA_EMBEDDING_MODEL, OLLAMA_BASE_URL,
    USE_HF_EMBEDDINGS, HF_EMBEDDINGS_MODEL, corpus_dir
)

def _embedding_fn():
    if USE_HF_EMBEDDINGS:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=HF_EMBEDDINGS_MODEL)
    if PROVIDER == "ollama":
        from langchain_community.embeddings import OllamaEmbeddings
        return OllamaEmbeddings(model=OLLAMA_EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
    else:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)

def create_corpus() -> str:
    """Crea un nuevo corpus en disco.

    Objetivo:
        Generar un identificador único y directorio en Chroma.

    Entrada:
        Ninguna.

    Salida:
        str: ID único del corpus.
    """
    cid = str(uuid.uuid4())
    os.makedirs(corpus_dir(cid), exist_ok=True)
    return cid

def upsert_texts(corpus_id: str, texts: List[str], metadatas: List[Dict]) -> None:
    """Inserta textos y metadatos en un corpus Chroma.

    Objetivo:
        Persistir embeddings y asociar información de contexto.

    Entrada:
        corpus_id (str): Identificador del corpus.
        texts (List[str]): Lista de chunks de texto.
        metadatas (List[Dict]): Metadatos por chunk.

    Salida:
        None
    """
    emb = _embedding_fn()
    vectordb = Chroma.from_texts(
        texts=texts, embedding=emb, metadatas=metadatas,
        persist_directory=corpus_dir(corpus_id)
    )
    vectordb.persist()

def get_db(corpus_id: str) -> Chroma:
    """Obtiene un manejador a la colección Chroma de un corpus.

    Objetivo:
        Permitir queries sobre la base vectorial persistida.

    Entrada:
        corpus_id (str): Identificador del corpus.

    Salida:
        Chroma: Objeto de base vectorial.
    """
    emb = _embedding_fn()
    return Chroma(persist_directory=corpus_dir(corpus_id), embedding_function=emb)
