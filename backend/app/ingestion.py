"""
app/ingestion.py

Objetivo del documento:
-----------------------
Módulo encargado de procesar documentos PDF: extraer texto por páginas,
dividirlo en chunks y generar metadatos para cada fragmento.

Responsabilidades clave:
- Lectura robusta de PDFs.
- Chunking configurable con solapamiento.
- Enriquecimiento de metadatos para auditoría y citas.
"""
from typing import Tuple, List, Dict
from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import io
import re

def _normalize_whitespace(text: str) -> str:
    # Opcional pero útil para consistencia del chunking
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def extract_pages(file_bytes: bytes) -> List[Tuple[int, str]]:
    """Extrae texto por página de un PDF.

    Objetivo:
        Obtener el contenido textual de cada página del PDF.

    Entrada:
        file_bytes (bytes): Contenido binario del PDF.

    Salida:
        List[Tuple[int, str]]: Lista de tuplas (número_de_página, texto).
    """
    bio = io.BytesIO(file_bytes)
    reader = PdfReader(bio)

    # Intentar desbloquear si viene cifrado
    try:
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:
                pass
    except Exception:
        pass

    pages: List[Tuple[int, str]] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append((i + 1, _normalize_whitespace(text)))
    return pages

def chunk_page_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120
) -> List[str]:
    """Divide el texto de una página en chunks.

    Objetivo:
        Asegurar que el contenido se procese en fragmentos manejables
        para embeddings y retrieval.

    Entrada:
        text (str): Texto de la página.
        chunk_size (int, opcional): Longitud máxima de cada chunk.
        chunk_overlap (int, opcional): Superposición de caracteres entre chunks.

    Salida:
        List[str]: Lista de fragmentos de texto.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    return splitter.split_text(text)

def build_chunks_from_pdf(
    file_bytes: bytes,
    filename: str,
    doc_hash: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120
) -> Tuple[List[str], List[Dict]]:
    """Construye chunks y metadatos por PDF.

    Objetivo:
        Generar los fragmentos de texto y metadatos enriquecidos
        que luego se insertan en Chroma.

    Entrada:
        file_bytes (bytes): Contenido binario del PDF.
        filename (str): Nombre del archivo.
        doc_hash (str): Hash único del documento.
        chunk_size (int): Tamaño máximo de chunk.
        chunk_overlap (int): Solapamiento entre chunks.

    Salida:
        Tuple[List[str], List[Dict]]:
            - Lista de textos (chunks).
            - Lista de metadatos (source, doc_hash, page, chunk_id, etc.).
    """
    pages = extract_pages(file_bytes)  # [(page_num, text)]
    texts: List[str] = []
    metas: List[Dict] = []

    # doc_id corto legible (no sensible, derivado de doc_hash)
    doc_id = doc_hash[:12]
    local_chunk_id = 0

    for page_num, page_text in pages:
        if not page_text:
            continue
        chunks = chunk_page_text(page_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for ch in chunks:
            texts.append(ch)
            metas.append({
                "source": filename,
                "doc_hash": doc_hash,
                "doc_id": doc_id,
                "page": page_num,              # <- página real
                "pages": str(page_num),        # <- campo usado por tu UI actual
                "chunk_id": local_chunk_id,    # <- secuencial por doc
            })
            local_chunk_id += 1

    # Si el PDF no tiene texto extraíble, deja al menos una entrada vacía para debug
    if not texts:
        texts.append("")  # o podrías omitir
        metas.append({
            "source": filename,
            "doc_hash": doc_hash,
            "doc_id": doc_id,
            "page": None,
            "pages": "",
            "chunk_id": 0,
        })

    return texts, metas
