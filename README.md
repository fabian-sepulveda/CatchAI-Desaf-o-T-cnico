# CatchAI – Backend FastAPI (mínimo viable)

Este backend provee 3 endpoints:
- `GET /health` → estado
- `POST /ingest` (multipart) → recibe 1–5 PDFs, indexa y devuelve `corpus_id`
- `POST /ask` (JSON) → recibe `corpus_id` y `question`, devuelve `answer` + `context`

## Ejecutar local
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # ajusta proveedor y modelos (ollama por defecto)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker
```bash
docker build -t catchai-backend .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data catchai-backend
```

## Ejemplos de uso (curl)

### Ingesta (subir PDFs)
```bash
curl -X POST http://localhost:8000/ingest   -F "files=@/ruta/doc1.pdf"   -F "files=@/ruta/doc2.pdf"
# => {"corpus_id":"<uuid>","chunks":123}
```

### Pregunta
```bash
curl -X POST http://localhost:8000/ask   -H "Content-Type: application/json"   -d '{"corpus_id":"<uuid>","question":"¿Cuál es el objetivo del documento?"}'
```

## Notas
- Por defecto `PROVIDER=ollama` y `USE_HF_EMBEDDINGS=true` (sin coste).
- Si `MOCK_MODE=true`, `/ask` devuelve una respuesta simulada (sin LLM).
- El índice Chroma se guarda en `/app/data/chroma/<corpus_id>` (monta volumen).

## Conectar con Streamlit (frontend)
- En tu app, primero `POST /ingest` con los archivos del uploader; guarda el `corpus_id` en `st.session_state`.
- Luego, en el chat, cada pregunta hace `POST /ask` con ese `corpus_id`.
