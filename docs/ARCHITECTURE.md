# Agentic‑RAG Math Professor – Technical Documentation

This document explains the system’s architecture, operations, and key decisions. It also captures the issues observed during development and how they were resolved.

## Goals
- Understand any math question and generate complete, step‑by‑step solutions.
- Always search the Knowledge Base (KB) first, then the web.
- Prioritize web search providers: MCP Tavily → LangChain Tavily → Tavily SDK.
- Generate the final answer using Gemini from the retrieved context.
- Provide input/output guardrails via an AI Gateway.
- Human‑in‑the‑loop feedback for self‑learning.
- UI shows sources and context in a collapsible area and renders clean, readable math (no raw LaTeX in answer text).

## High‑level architecture

```
User → Frontend (React) → Backend (FastAPI)
                                │
                                ├─ Input guardrails
                                ├─ Retrieval: Weaviate KB (VectorStore)
                                ├─ Web Search: MCP Tavily → LangChain Tavily → Tavily SDK
                                ├─ Orchestration: LangGraph (state + routing)
                                ├─ Generation: DSPy + Gemini (CoT; complete answers)
                                ├─ Output guardrails
                                └─ Feedback store (JSON)
```

### Core components
- LangGraph workflow (`app/workflows/langgraph_pipeline.py`)
  - Nodes: input guardrails → KB retrieval → web search → generation → output guardrails.
  - Routing: even when KB is strong, we still perform a web search to enrich context.
  - State includes `kb_hits`, `web_hits`, `knowledge_hits` (combined), `search_result`, `citations`.
- Vector store (`app/services/vector_store.py`)
  - Weaviate v4 client; robust schema detection supporting both legacy and new property names.
  - Query returns similarity and properties in a normalized shape.
- Web search (`app/tools/web_search.py`)
  - Priority: MCP Tavily → LangChain Tavily → Tavily SDK.
  - MCP integration sends `Accept: text/event-stream, application/json`, parses SSE, and tries multiple JSON‑RPC shapes.
  - Deduplication by URL; aims to aggregate up to 5 documents.
- Generation (`app/tools/dspy_pipeline.py`)
  - DSPy + Gemini with explicit prompts for complete, natural‑language solutions and clear final answers.
  - Increased `max_output_tokens` for completeness; normalization removes markdown noise and LaTeX tokens.
- Guardrails (`app/guardrails.py`)
  - Input: permits math; blocks PII/blocked keywords.
  - Output: permissive; avoids blocking legitimate math.
- Settings (`app/config.py`)
  - `.env` discovery across multiple locations.
  - KB threshold aliases: `SIMILARITY_THRESHOLD`, `KB_SIMILARITY_THRESHOLD`, `KB_THRESHOLD`.

## Data flow (request)
1. Frontend sends the question to `/api/agent/query`.
2. Input guardrails sanitize the text (if enabled).
3. KB retrieval against Weaviate returns top‑k hits; stored as `kb_hits`.
4. Router logs top similarity and proceeds to web search regardless of threshold (to enrich context).
5. Web search runs providers in priority order, aggregates results, and records `citations`.
6. DSPy + Gemini generate steps and an answer using all contexts.
7. Output guardrails optionally filter unsafe elements; citations are merged.
8. Response returned to frontend with `answer`, `steps`, `citations`, `knowledge_hits`, `source`, and `gateway_trace`.

## Frontend rendering
- Explanation shown once under “Solution”.
  - Steps are bullets; otherwise the raw content is split into bullet points.
- Answer displayed as a highlighted, concise block (extracts from `Final Answer`/`Answer` or last evaluated value).
- “Sources & Context” is collapsed by default and shows KB snippets and citations.

## Environment & configuration
- Set in `backend/.env` (or repo `.env`). Important keys:
  - `WEAVIATE_URL`, `WEAVIATE_API_KEY`, `WEAVIATE_COLLECTION`
  - `TAVILY_API_KEY`, `MCP_TAVILY_URL`
  - `GEMINI_API_KEY`
  - `SIMILARITY_THRESHOLD` (or `KB_SIMILARITY_THRESHOLD` / `KB_THRESHOLD`)
- Threshold tuning: increase to bias toward stronger KB matches; UI still enriches via web.

## Known issues and resolutions
- Weaviate v4 gRPC health check timeout → allow gRPC 443 or disable init check/raise timeout.
- `near_vector(vector=...)` API mismatch → updated to `near_vector=...`; removed `.do()`.
- Legacy schema properties → dynamic detection; fallback queries.
- MCP 406 Not Acceptable → correct `Accept` header and SSE parsing.
- Random web results → ensure sanitized query is passed consistently; unify parsers.
- Duplicated explanations in UI → render logic updated to show explanation once and separate concise Answer.

## Human‑in‑the‑loop
- Feedback endpoint persists JSON (`backend/data/feedback_db.json`).
- Thumbs up/down and optional better solution text/images/PDF can be used to finetune prompts or seed KB updates.

## Local development
- Backend: `poetry install && poetry run uvicorn app.main:app --reload --port 8000`
- Frontend: `npm install && npm run dev`
- Ensure `.env` contains valid keys; verify MCP endpoint reachability with a HEAD request.

## Extensibility
- Add new search providers by implementing a function returning `WebDocument[]` and chaining it after existing sources.
- Swap vector DB: implement the same `VectorStore` interface.
- Add tool use (e.g., calculators) via additional LangGraph nodes before generation.

## Security & privacy
- Guardrails enforce PII blocking; expand `blocked_keywords` as needed.
- Do not log full queries/answers in production; route logs are present for debugging locally.

## Testing checklist
- KB retrieval returns hits for seeded questions.
- Web search returns at least two results when network/API keys are valid.
- UI shows one explanation and a concise Answer.
- Guardrails allow math but block obvious PII/blocked keywords.


