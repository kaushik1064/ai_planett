# Math Agentic RAG – Final Proposal

## Guardrails & AI Gateway Integration
- **Input guardrails**: Sanitises user text, blocks non-math intents, detects PII before routing.
- **Output guardrails**: Scrubs generated answers, enforces math-only tone, surfaces citations.
- **AI Gateway abstraction**: All agent calls flow through `MathAgent.handle_query`, capturing gateway trace metadata used by the frontend.

## Knowledge Base
- **Dataset**: `backend/data/knowledge_base.jsonl` (GSM8K/GRE-style foundational algebra, calculus, probability problems).
- **Vector store**: Built via `scripts/build_kb.py` using `SentenceTransformer` embeddings + FAISS.
- **Sample queries**:
  1. "Solve for x: 2x + 5 = 17"
  2. "Simplify: (x^2 - 9)/(x - 3)"
  3. "Evaluate the derivative of 3x^3 - 4x^2 + x - 7"

## Web + MCP Search Pipeline
- **Primary**: Tavily MCP server (`backend/mcp_servers/tavily_server.py`) accessed via stdio JSON-RPC.
- **Fallback**: Gemini 2.5 Flash grounded search when Tavily fails or lacks coverage.
- **Example queries**:
  1. "What is the latest JEE Main exam pattern?"
  2. "Find the binomial theorem applications in real-world examples"
  3. "Recent advancements in non-linear differential equations"

## Human-in-the-Loop & Feedback
- **Feedback UX**: Mandatory thumbs-up/down with negative reason capture, optional solution upload.
- **Storage**: `feedback_db.json` for raw signals, `kb_candidate_queue.json` for validated user solutions.
- **Validation**: Gemini-based checking (`tools/validator.py`) before routing to curator queue.

## DSPy & Reasoning
- **LangGraph workflow**: `app/workflows/langgraph_pipeline.py` encodes guardrails → KB search → web fallback → DSPy reasoning → output moderation as a stateful graph.
- **DSPy generation**: `tools/dspy_pipeline.py` uses Gemini via DSPy to emit structured step-by-step reasoning JSON.

## Voice & Vision Modalities
- **Speech**: Groq Whisper transcription (`tools/audio.py`).
- **Image**: Gemini multimodal OCR (`tools/vision.py`).

## Deployment Notes
- FastAPI app exposed at `/api/chat`, `/api/feedback`, `/api/benchmark` with CORS enabled for React frontend.
- Environment variables: `GEMINI_API_KEY`, `TAVILY_API_KEY`, `GROQ_API_KEY`.
- Frontend interacts via `VITE_API_BASE`.

