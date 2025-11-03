# Frontend – Agentic RAG Math Professor UI

Vite + React single‑page app for chatting with the math professor. It renders step‑by‑step solutions clearly, shows a highlighted final answer, and provides a collapsible Sources & Context area (KB snippets and citations).

## Install & run

```bash
# from frontend/
npm install
npm run dev
# open the URL printed by Vite (default http://localhost:5173)
```

Environment (optional):
- By default the app calls the backend at `http://localhost:8000`. If you proxy/change base URL, update your fetch client accordingly.

## UI behavior
- Explanation: shown once under “Solution”.
  - If structured steps are present, they are rendered as bullet points.
  - Otherwise, the message text is rendered as bullet points.
- Answer: highlighted block with a concise final result (e.g., `10` or `14 ln|x| + C`).
- Sources & Context: collapsible; displays KB snippets with similarity and web citations.
- Feedback: thumbs up/down with optional improved solution inputs.

## Developer notes
- `src/components/ChatMessage.tsx`: presentation of messages (steps as bullets, answer highlighting, duplicate‑explanation suppression).
- `src/types.ts`: shared types for messages, steps, citations.
- Styling: Tailwind‑like utility classes; gradients and subtle borders for readability.

## Common issues
- Duplicated explanations: ensure latest `ChatMessage.tsx`; the component hides `Answer:` lines inside steps and keeps a single Answer block.
- Long math paragraphs: the renderer splits content into line‑by‑line items.

---

See `../docs/ARCHITECTURE.md` for the full backend + frontend architecture and operational notes.
  