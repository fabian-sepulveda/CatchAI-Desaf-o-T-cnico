import os
import io
import requests
import streamlit as st
from typing import List

# =========================
# Config
# =========================
# Se realiza la configuración de la página, como titulo de esta.
st.set_page_config(page_title="CCsD - Copiloto Conversacional sobre Documentos", layout="wide")
# Se indica el URL al que esta conectado el backend, para mostrar los valores de salud de este.
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000") 

# =========================
# Session state
# =========================
# Se inician los estados de la página, de esta forma llevar un control de la ingesta de archivos, y controlar las acciones que se le permiten al usuario.
def init_state():
    if "messages" not in st.session_state: # Control de mensajes del chat
        st.session_state.messages = []
    if "docs" not in st.session_state: # Control de documentos
        st.session_state.docs = []
    if "corpus_id" not in st.session_state: # Control de procesamiento de chunks
        st.session_state.corpus_id = None
    if "ingest_done" not in st.session_state: # Control de ingesta de información en backend
        st.session_state.ingest_done = False
    if "upload_key" not in st.session_state: # Control de subida de archivos
        st.session_state.upload_key = 0

init_state()

# =========================
# Sidebar
# =========================
# En el sidebar se busca mostrar el estado de la pagina, como Documentos cargados, link de backend y la salud de este.
# Se dispone un boton de reinicio, para comenzar un nuevo flujo conversacional.
with st.sidebar:
    st.header("⚙️ Estado")
    st.write(f"PDFs cargados: **{len(st.session_state.docs)}** ")
    st.write(f"Backend: {BACKEND_URL}")
    health_ok = False
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=5)
        health_ok = r.ok
    except Exception:
        health_ok = False
    st.markdown(f"Salud backend: {'🟢 OK' if health_ok else '🔴 Caído'}")
    
    if st.button("🔄 Reiniciar sesión"):
        # (Opcional) Si quieres pedirle al backend que borre el corpus en disco:
        if st.session_state.corpus_id:
            try:
                requests.post(f"{BACKEND_URL}/reset", json={"corpus_id": st.session_state.corpus_id}, timeout=10)
            except Exception:
                # Si no existe el endpoint /reset o falla, seguimos sin bloquear el reset del frontend
                pass

        # Limpieza total del estado del frontend
        st.session_state.messages = []
        st.session_state.docs = []
        st.session_state.corpus_id = None
        st.session_state.ingest_done = False

        # Forzar que el file_uploader se recree vacío
        st.session_state.upload_key += 1

        # Refrescar la UI al estado inicial
        st.rerun()

# =========================
# Header
# =========================
st.title("🧠 Copiloto Conversacional sobre Documentos")

# =========================
# Upload PDFs
# =========================
# Sección de subida de Documentos PDF, en esta se permite la subida de documentos, en particular se permite la subida de cualquier archivo,
# pero esto se puede limitar en caso de ser necesario. 
# Una vez los archivos hayan sido seleccionados y ingestados al backend, esta sección se bloquea y desaparece para guiar al usuario al chatbot
if not st.session_state.ingest_done:
    st.subheader("Cargar PDFs")
    uploaded: List[st.runtime.uploaded_file_manager.UploadedFile] = st.file_uploader(
        "Selecciona tus archivos (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.upload_key}",
        help="Puedes cargar varios PDFs. Luego presiona 'Procesar documentos'."
    )

    if uploaded:
        st.session_state.docs = [
            {"name": uf.name, "size_kb": round(len(uf.getvalue())/1024, 2)}
            for uf in uploaded
        ]
        st.success(f"Se cargaron {len(st.session_state.docs)} archivo(s) correctamente.")

    if st.session_state.docs:
        st.write("**Archivos cargados:**")
        st.dataframe(st.session_state.docs, use_container_width=True)

        # Botón de ingesta al backend (Con este boton se realiza la subida de información, una vez procesado se oculta la sección de subida)
        if st.button("🚀 Procesar documentos"):
            if not uploaded:
                st.error("No hay archivos en memoria. Vuelve a subirlos.")
            else:
                files = [("files", (uf.name, uf.getvalue(), "application/pdf")) for uf in uploaded]
                try:
                    with st.spinner("Procesando..."):
                        resp = requests.post(f"{BACKEND_URL}/ingest", files=files, timeout=300)
                    if resp.ok:
                        data = resp.json()
                        st.session_state.corpus_id = data.get("corpus_id")
                        st.session_state.ingest_done = True
                        st.success(
                            f"Índice listo. corpus_id: {st.session_state.corpus_id} "
                            f"(chunks: {data.get('chunks')})"
                        )
                        st.rerun()  # refresca la vista y oculta la sección de subida
                    else:
                        st.error(f"Error de ingesta: {resp.status_code} - {resp.text}")
                except Exception as e:
                    st.error(f"No se pudo contactar al backend: {e}")
else:
    # Tras ingestar, NO mostramos la sección de subida
    st.success("✅ Documentos procesados. Puedes continuar con el chat.")
    # Mostrar lista en modo lectura
    if st.session_state.docs:
        with st.expander("Ver documentos procesados"):
            st.dataframe(st.session_state.docs, use_container_width=True)
# =========================
# Chat (solo si hay corpus_id)
# =========================
# El chat solo se muestra si poseemos el estado del corpus_id, de esta forma nos aseguramos que la información a sido cargada correctamente.
if st.session_state.ingest_done and st.session_state.corpus_id:
    st.subheader("Chat")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Escribe tu pregunta sobre los documentos")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Llamada al backend /ask
        payload = {"corpus_id": st.session_state.corpus_id, "question": prompt}
        try:
            with st.spinner("Consultando..."):
                r = requests.post(f"{BACKEND_URL}/ask", json=payload, timeout=120)
            if r.ok:
                data = r.json()
                answer = data.get("answer", "(Sin respuesta)")
                with st.chat_message("assistant"):
                    st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

                # Mostrar contexto como expander
                ctx = data.get("context", [])
                if ctx:
                    with st.expander("Contexto usado"):
                        for i, c in enumerate(ctx):
                            st.markdown(f"- ({i+1}) **{c.get('source')}**, páginas: {c.get('pages')}")
            else:
                err = f"Error {r.status_code} — {r.text}"
                with st.chat_message("assistant"):
                    st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})
        except Exception as e:
            with st.chat_message("assistant"):
                st.error(f"No se pudo contactar al backend: {e}")
            st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})

else:
    st.info("💡 Sube al menos un PDF y presiona **Procesar documentos** para habilitar el chat.")
