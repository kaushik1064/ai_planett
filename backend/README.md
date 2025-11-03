# Backend – Agentic RAG Math Professor

This service is a FastAPI backend that powers an Agentic‑RAG math tutor. It orchestrates guardrailed input/output, retrieves from a Weaviate knowledge base, performs prioritized web search (MCP Tavily → LangChain Tavily → Tavily SDK), and generates step‑by‑step solutions with Gemini via a DSPy pipeline. It exposes HTTP endpoints for the frontend and records feedback for human‑in‑the‑loop learning.

## Quick start

```bash
# from project root or backend/
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

If you use a venv directly:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -U -r requirements.txt  # if you export one with poetry export
uvicorn app.main:app --reload --port 8000
```

## Configuration

Configuration is loaded from environment variables and `.env`. The loader searches in:
- repo root: `.env`
- `backend/.env`
- current working directory

Key variables:
- WEAVIATE_URL: Weaviate Cloud URL
- WEAVIATE_API_KEY: Weaviate API key
- WEAVIATE_COLLECTION: Default `mathvectors`
- TAVILY_API_KEY: Tavily API key
- MCP_TAVILY_URL: Remote MCP endpoint for Tavily (e.g. `https://mcp.tavily.com/mcp/?tavilyApiKey=...`)
- GEMINI_API_KEY: Google Generative AI key
- SIMILARITY_THRESHOLD or KB_SIMILARITY_THRESHOLD or KB_THRESHOLD: float (e.g. `0.75`)

Other toggles:
- ENFORCE_INPUT_GUARDRAILS=true|false (default true)
- ENFORCE_OUTPUT_GUARDRAILS=true|false (default true)

## Weaviate notes (v4 client)
- The client uses the v4 API. gRPC health check may fail in some networks. If startup fails with `WeaviateGRPCUnavailableError`, either:
  - allow outbound 443 to `grpc-<cluster>.weaviate.cloud`, or
  - set the connection to skip init checks in code (already supported) and proceed, or
  - increase init timeout.
- Collection properties handled dynamically: supports old (`input/label/source_file`) and new (`question/answer/source`) schemas.

## Retrieval and search
- KB retrieval: Weaviate vector search using SentenceTransformers embeddings.
- Web search priority:
  1) Tavily via MCP (SSE/JSON‑RPC handled)
  2) LangChain Tavily tool
  3) Tavily SDK
- At least ~5 combined documents are aggregated (deduped by URL) when possible.

## Generation
- DSPy + Gemini with explicit chain‑of‑thought prompting (no raw LaTeX; natural language; complete, wrapped answers). Max output tokens increased for completeness.
- The system always generates from all available context (KB + web). If no context is found, it still answers, but the UI hides that detail by design.

## Guardrails (AI Gateway semantics)
- Input: permissive for mathematics; blocks PII and configured `blocked_keywords`.
- Output: permissive; blocks PII/blocked keywords; preserves math terms. Empty/short responses are allowed.

## Endpoints (high‑level)
- POST `/api/agent/query` – main entry; accepts a math question (and optional modalities); returns `answer`, `steps`, `citations`, `knowledge_hits`, `source`, `gateway_trace`.
- POST `/api/agent/feedback` – records thumbs‑up/down and optional better solution assets into `backend/data/feedback_db.json`.

## Running locally
1) Create `backend/.env` with at least:
```
WEAVIATE_URL=...
WEAVIATE_API_KEY=...
TAVILY_API_KEY=tvly-...
MCP_TAVILY_URL=https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-...
GEMINI_API_KEY=...
SIMILARITY_THRESHOLD=0.80
```
2) `poetry install`
3) `poetry run uvicorn app.main:app --reload --port 8000`

## Troubleshooting
- gRPC deadline exceeded on startup: see Weaviate notes above.
- MCP 406 Not Acceptable: ensure `Accept: text/event-stream, application/json` and correct URL; we send these headers by default.
- MCP unreachable: verify `MCP_TAVILY_URL` and network; try `Invoke-WebRequest` HEAD to the URL.
- Tavily unauthorized: check `TAVILY_API_KEY` format and that the env is loaded.
- Long answers are not wrapping: frontend renders line‑by‑line and bullets; ensure you’re on latest UI.

## Project layout (backend)
- `app/config.py` – settings loader with multi‑path .env and threshold aliases
- `app/services/vector_store.py` – Weaviate operations and schema auto‑detection
- `app/tools/web_search.py` – MCP/LangChain/SDK web search with priority
- `app/tools/dspy_pipeline.py` – DSPy + Gemini solution generator
- `app/workflows/langgraph_pipeline.py` – LangGraph orchestration
- `app/guardrails.py` – input/output guardrails
- `app/schemas.py` – Pydantic models
- `app/main.py` – FastAPI app wiring

---

For a deeper architectural explanation, see `../docs/ARCHITECTURE.md`.
# Math Agent Backend

## Setup

1. Install dependencies (Poetry):
   ```bash
   cd backend
   poetry install
   ```

2. Create `.env` in `backend/`:
   ```env
   GEMINI_API_KEY=your_key
   TAVILY_API_KEY=your_key
   GROQ_API_KEY=your_key
   ```

3. Build the knowledge base:
   ```bash
   poetry run python scripts/build_kb.py
   ```

4. Run the FastAPI app:
   ```bash
   poetry run uvicorn app.main:app --reload --port 8000
   ```

   The service uses a LangGraph-based orchestration layer (`app/workflows/langgraph_pipeline.py`) to coordinate guardrails, KB retrieval, web fallback, and response generation.

## Endpoints

- `POST /api/chat` – Main chat endpoint (handles text, audio, image inputs).
- `POST /api/feedback` – Stores user feedback + triggers validation workflow.
- `GET /api/benchmark` – Runs JEE bench evaluation (optional `?limit=`).
- `GET /api/vector-store/reload` – Reload FAISS index after ingestion.
- `GET /health` – Health status.

## MCP Tavily Search

To expose Tavily via MCP (stdio):

```bash
python backend/mcp_servers/tavily_server.py
```

The backend spawns this server per request; you can also host it separately and point `web_search.py` to the running instance.


