"""
app/main.py

Objetivo del documento:
-----------------------
Exponer la API REST principal con FastAPI. Gestiona la ingesta de PDFs en un corpus,
la persistencia en Chroma y la generación de respuestas con LLM usando retrieval.

Responsabilidades clave:
- Endpoints para ingesta, consulta y health-check.
- Validación de inputs y control de errores HTTP.
- Orquestar funciones de `ingestion`, `store` y `qa`.

Dependencias relevantes:
- fastapi, pydantic, hashlib
- módulos locales: ingestion, store, qa, config
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import hashlib
import os, shutil

from .config import corpus_dir
from .ingestion import build_chunks_from_pdf

from .store import create_corpus, upsert_texts
from .qa import answer

app = FastAPI(title="CatchAI Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class IngestResponse(BaseModel):
    corpus_id: str
    chunks: int

class AskRequest(BaseModel):
    corpus_id: str
    question: str

class AskResponse(BaseModel):
    answer: str
    context: list

class ResetRequest(BaseModel):
    corpus_id: str


@app.get("/health")
def health():
    """
    app/main.py

    Objetivo del documento:
    -----------------------
    Exponer la API REST principal con FastAPI. Gestiona la ingesta de PDFs en un corpus,
    la persistencia en Chroma y la generación de respuestas con LLM usando retrieval.

    Responsabilidades clave:
    - Endpoints para ingesta, consulta y health-check.
    - Validación de inputs y control de errores HTTP.
    - Orquestar funciones de `ingestion`, `store` y `qa`.

    Dependencias relevantes:
    - fastapi, pydantic, hashlib
    - módulos locales: ingestion, store, qa, config
    """
    return {"status":"ok"}

@app.post("/ingest", response_model=IngestResponse)
async def ingest(files: List[UploadFile] = File(...)):
    """Ingesta documentos PDF y los persiste en un corpus Chroma.

    Objetivo:
        Recibir uno o más PDFs, extraer texto por páginas,
        dividir en chunks, generar metadatos y almacenar embeddings en Chroma.

    Entrada:
        files (List[UploadFile]): Archivos PDF subidos en multipart form-data.

    Salida:
        IngestResponse: Objeto con `corpus_id` y número total de chunks procesados.

    Excepciones:
        HTTPException: Si no hay archivos, si exceden el límite permitido
        o si un archivo no es PDF válido.
    """

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Debes subir al menos un PDF")

    texts, metas = [], []
    cid = create_corpus()
    total_chunks = 0

    # (Opcional) registrar un manifest con la lista exacta de PDFs
    doc_entries = []
    print("############################")
    print("archivos recibidos en el backend")
    print(files)
    print("############################")

    for uf in files:
        if uf.content_type not in ("application/pdf", "application/x-pdf"):
            raise HTTPException(status_code=400, detail=f"Archivo no PDF: {uf.filename}")

        raw = await uf.read()
        digest = hashlib.sha256(raw).hexdigest()

        # --- NUEVO: chunking por página con metadatos ricos ---
        t_i, m_i = build_chunks_from_pdf(
            file_bytes=raw,
            filename=uf.filename,
            doc_hash=digest,
            chunk_size=800,       # puedes tunear estos dos
            chunk_overlap=120
        )
        texts.extend(t_i)
        metas.extend(m_i)
        total_chunks += len(t_i)

        # (Opcional) llenar manifest: filename, hash y #páginas
        try:
            from pypdf import PdfReader
            import io
            n_pages = len(PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            n_pages = None
        doc_entries.append({"filename": uf.filename, "doc_hash": digest, "pages": n_pages})

    # Persistir en Chroma
    upsert_texts(cid, texts, metas)

    # (Opcional) escribir manifest.json junto al índice
    try:
        import json, os
        manifest_path = os.path.join(corpus_dir(cid), "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"documents": doc_entries}, f, ensure_ascii=False, indent=2)
    except Exception:
        # no bloquee la ingesta si falla el manifest
        pass

    return IngestResponse(corpus_id=cid, chunks=total_chunks)

@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest):
    """Responde preguntas usando retrieval + LLM.

    Objetivo:
        Dado un corpus ya indexado y una pregunta, recuperar el contexto relevante
        y generar una respuesta natural con citas.

    Entrada:
        payload (AskRequest): Objeto con:
            - corpus_id (str): Identificador del corpus.
            - question (str): Pregunta del usuario.

    Salida:
        AskResponse: Objeto con:
            - answer (str): Respuesta generada.
            - context (List[dict]): Fragmentos recuperados (fuente, páginas, etc.).
    """
    if not payload.corpus_id:
        raise HTTPException(status_code=400, detail="corpus_id es requerido")
    ans, ctx = answer(payload.corpus_id, payload.question)
    return AskResponse(answer=ans, context=ctx)

@app.post("/reset")
async def reset_corpus(payload: ResetRequest):
    """
    Objetivo:
        Elimina físicamente el directorio asociado a un corpus previamente
        creado en el backend. Este endpoint se utiliza normalmente cuando
        el usuario desea reiniciar la sesión desde el frontend y borrar
        el índice/corpus en disco.

    Entrada:
        payload (ResetRequest):
            - corpus_id (str): Identificador único del corpus que se quiere
              eliminar del sistema.

    Salida:
        dict: Respuesta en formato JSON con la siguiente estructura:
            - status (str): "ok" si la eliminación fue exitosa, "error" si ocurrió
              un problema.
            - message (str): Mensaje descriptivo del resultado de la operación,
              indicando el corpus eliminado o el error detectado.
    """
    cid = payload.corpus_id
    path = corpus_dir(cid)
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
        return {"status": "ok", "message": f"Corpus {cid} eliminado"}
    except Exception as e:
        # No bloquear: devolvemos error pero el frontend igual puede resetear su estado
        return {"status": "error", "message": str(e)}