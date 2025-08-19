"""
app/qa.py

Objetivo del documento:
-----------------------
Orquestar retrieval + prompting y generar respuestas con el LLM.

Responsabilidades clave:
- Recuperación de contexto relevante.
- Construcción de prompts.
- Invocación al LLM configurado.
- Formateo de respuestas con citas.
"""
from typing import List, Dict, Tuple
from .store import get_db
from .config import PROVIDER, OLLAMA_MODEL, OLLAMA_BASE_URL, OPENAI_MODEL, MOCK_MODE


def retrieve_context_balanced(corpus_id: str, query: str, k: int = 8, per_doc: int = 1):
    """Recupera fragmentos relevantes para la consulta.

    Objetivo:
        Usar la base vectorial para traer los k documentos más similares.

    Entrada:
        corpus_id (str): ID del corpus a consultar.
        query (str): Pregunta del usuario.
        k (int, opcional): Número de fragmentos a recuperar.

    Salida:
        List[Dict]: Lista de fragmentos con texto y metadatos.
    """
    db = get_db(corpus_id)
    # Trae más candidatos de los que vas a usar
    retriever = db.as_retriever(
        search_type="mmr",
        search_kwargs={"k": max(k, 12), "fetch_k": max(3*k, 24)}
    )
    docs = retriever.get_relevant_documents(query)

    # Convierte a dicts
    cands = [{
        "text": d.page_content,
        "source": d.metadata.get("source"),
        "pages": d.metadata.get("pages"),
        "page": d.metadata.get("page"),
        "chunk_id": d.metadata.get("chunk_id"),
        "doc_hash": d.metadata.get("doc_hash"),
    } for d in docs]

    # Agrupa por documento
    by_doc = {}
    for c in cands:
        key = (c.get("source"), c.get("doc_hash"))
        by_doc.setdefault(key, []).append(c)

    # Toma hasta `per_doc` por documento (para diversificar)
    balanced = []
    for key, items in by_doc.items():
        balanced.extend(items[:per_doc])

    # Si faltan para llegar a k, rellena con los mejores restantes
    #   (los cands que no quedaron en `balanced`)
    taken_ids = {(c["source"], c["doc_hash"], c["chunk_id"]) for c in balanced}
    rest = [c for c in cands if (c["source"], c["doc_hash"], c["chunk_id"]) not in taken_ids]

    final = balanced[:k]
    if len(final) < k:
        final.extend(rest[:(k - len(final))])

    # Dedup final por doc/chunk por seguridad
    seen = set()
    dedup = []
    for c in final:
        key = (c["source"], c["doc_hash"], c["chunk_id"])
        if key in seen: 
            continue
        seen.add(key)
        dedup.append(c)

    return dedup[:k]



def _llm():
    """
    Objetivo:
        Inicializa y devuelve un modelo de lenguaje (LLM) según el proveedor
        configurado en la aplicación. Soporta tanto Ollama como OpenAI, 
        seleccionando dinámicamente la librería adecuada.

    Entrada:
        No recibe parámetros directamente. Utiliza las variables de configuración
        globales:
            - PROVIDER (str): Define el proveedor a usar ("ollama" u "openai").
            - OLLAMA_MODEL (str): Nombre del modelo Ollama si PROVIDER == "ollama".
            - OLLAMA_BASE_URL (str): Endpoint base para conectar con Ollama.
            - OPENAI_MODEL (str): Nombre del modelo OpenAI si PROVIDER != "ollama".

    Salida:
        langchain_community.chat_models.ChatOllama o 
        langchain_openai.ChatOpenAI:
            Instancia del modelo de lenguaje configurado, lista para ejecutar
            operaciones de conversación o generación de texto.
    """
    if PROVIDER == "ollama":
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=OPENAI_MODEL, temperature=0)

from typing import List, Dict, Tuple

def answer(corpus_id: str, question: str) -> Tuple[str, List[Dict]]:
    """Genera una respuesta con contexto usando el LLM.

    Objetivo:
        Combinar retrieval + LLM para entregar una respuesta natural
        con citas a documentos fuente.

    Entrada:
        corpus_id (str): Corpus en que se consulta.
        question (str): Pregunta del usuario.

    Salida:
        Tuple[str, List[Dict]]:
            - Respuesta final (str).
            - Fragmentos de contexto usados (List[Dict]).
    """
    if MOCK_MODE:
        demo = "Modo demo: respuesta simulada. Integraremos LLM real cuando desactives MOCK_MODE."
        ctx = [{"text": "Fragmento simulado", "source": "demo.pdf", "pages": "1-2", "chunk_id": 0}]
        return demo, ctx

    ctx = retrieve_context_balanced(corpus_id, question)

    if not ctx:
        return "No encuentro información relevante en los documentos cargados.", []

    # 🔎 Debug: mostrar qué contexto se está entregando
    print("=== CONTEXTO ENVIADO AL LLM ===")
    for c in ctx:
        print(f"[{c['source']} | {c.get('pages')}] chunk={c['chunk_id']} -> {c['text'][:120]}...")
    print("=== FIN DEL CONTEXTO ===\n")

    # Construcción de prompt
    context_str = "\n\n".join([f"[{c['source']} | {c['pages']}]\n{c['text']}" for c in ctx])
    prompt = (
        "Eres un asistente experto en análisis de documentos PDF. "
        "Debes trabajar EXCLUSIVAMENTE con el contexto entregado. "
        "Si la información solicitada no está en el contexto, indícalo de forma clara.\n\n"

        "Tu respuesta debe ser clara, natural y estructurada, evitando frases robóticas. "
        "Adapta tu estilo según el tipo de solicitud:\n"
        "- Si se pide un RESUMEN: entrega un texto breve, coherente y fácil de leer.\n"
        "- Si se pide una COMPARACIÓN entre documentos: organiza las diferencias y similitudes en párrafos o viñetas.\n"
        "- Si se pide una CLASIFICACIÓN o agrupación por temas: genera categorías con títulos claros y lista los elementos bajo cada una.\n\n"

        f"=== CONTEXTO DISPONIBLE ===\n{context_str}\n\n"
        f"=== PREGUNTA ===\n{question}\n\n"

        "Al final de tu respuesta, incluye siempre 2–4 citas de apoyo en el formato: "
        "(Documento: <nombre>, páginas: X–Y)."
    )


    llm = _llm()
    resp = llm.invoke([{"role": "user", "content": prompt}])
    return resp.content, ctx
