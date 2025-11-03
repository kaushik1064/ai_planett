# Agentic RAG Math Professor

An **AI-powered math tutoring platform** with advanced Agentic-RAG orchestration, step-by-step solutions via Gemini, scalable vector retrieval (Weaviate), prioritized web search (MCP Tavily, LangChain), and feedback-driven human-in-the-loop improvement.

***

## Architecture Overview

- **Backend**: FastAPI orchestrates guardrails, knowledge base retrieval (via Weaviate), prioritized web search (MCP Tavily → LangChain → SDK), and DSPy+Gemini chain-of-thought stepwise generation. All endpoints support feedback for continual model improvement.
- **Frontend**: Vite+React single-page app for interactive chat, rich step-by-step explanations, contextual citations, and feedback collection.

***

## Quick Start (Local)

> Clone this repo and run locally for full-stack dev!

**Backend:**
```bash
cd backend
conda create -p venv python==3.13 -y
poetry install
cp .env.example .env    # Set your secrets!
poetry run uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` and chat with your AI math professor!

***

## Configuration

- Place all secrets (API keys, service URLs) in `backend/.env`. Supported variables:
  - `WEAVIATE_URL` (Weaviate endpoint)
  - `WEAVIATE_API_KEY`
  - `GROQ_API_KEY`(for whisper model which help in audio input)
  - `TAVILY_API_KEY`
  - `MCP_TAVILY_URL`
  - `GEMINI_API_KEY`
  - `SIMILARITY_THRESHOLD`, `ENFORCE_INPUT_GUARDRAILS`, `ENFORCE_OUTPUT_GUARDRAILS` (boolean toggles)

***

## Key Endpoints

- `POST /api/agent/query` — Main chat, math questions in, step-by-step answers out
- `POST /api/agent/feedback` — Signal good/bad answers to improve the agent
- `GET /health` — Health status

See Swagger docs at `/docs` after starting the backend.

***

## Weaviate & Search Pipeline

- KB retrieval via vector search (SentenceTransformers, adjustable similarity threshold)
- Web search priority: MCP Tavily (SSE/JSON‑RPC) → LangChain tool → Tavily SDK

***

## DSPy + Gemini Solution Generation

- Generates from all KB + web context (never answers blind unless no context)
- Chain-of-thought step explanations
- Full pipeline in `app/tools/dspy_pipeline.py`

***

## Guardrails: Input/Output Filtering

- Input blocks PII/keywords, allows rich math
- Output ensures clarity/safety, blocks sensitive terms

***

## Feedback Loop

- All answers recorded with feedback in `backend/data/feedback_db.json` (can be hooked to dashboards or retraining loader)

***

## Running on the Cloud

### Deploy Backend (AWS EC2/Render)

- **AWS EC2**: See deployment instructions in this README (or [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md))
  - Install Poetry & Python
  - Configure `.env`
  - `poetry install` then `poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Render**:
  1. Push repo to GitHub
  2. Create new Web Service from `backend/`
  3. Add env vars, confirm build/start commands (see `render.yaml`)
  4. Hit the generated Render URL (API for frontend)

### Deploy Frontend (Vercel)

- Push `frontend/` to GitHub
- New Vercel project (Framework: Vite)
- Build: `npm run build` (output: `dist`)
- Set `VITE_BACKEND_BASE_URL` in Vercel to your backend service endpoint (AWS or Render)
- Done! Share the Vercel link.

***

## Project Layout

```
backend/
  app/
    main.py              # FastAPI entry point
    config.py            # .env & simple settings loader
    services/            # Vector store, search, pipeline logic
    tools/               # MCP, DSPy, LangChain ops
    workflows/           # LangGraph orchestration
    guardrails.py        # Blocking keywords, sensitive data
    schemas.py           # Pydantic models
  scripts/
    build_kb.py          # Custom knowledge base builder
  data/
    feedback_db.json     # Local feedback & signal storage
  .env.example           # Template for configuration
  render.yaml            # Render deploy config

frontend/
  src/
    components/ChatMessage.tsx  # Main message renderer
    types.ts                    # Shared message/citation types
    # Tailwind-like classes + clean UI logic
  vercel.json           # Vercel deploy config
```

***

MIT — Open source, build your own agentic tutor, contribute!
  
***

**Get started, get answers, and help improve math learning with AI!**

***

Paste this README in your repo root and you’ll have an instantly impressive, clear, and complete intro for any visitor or collaborator. Let me know if you want it tailored for a specific team/company badge or API usage diagram!
