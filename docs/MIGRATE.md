# Migrate screen-scribe-pilot from n8n to a CrewAI FastAPI service

## Context

The frontend (Vite + React + TS, deployed on Vercel) currently calls **8 hardcoded n8n webhook URLs** scattered across 6 page components. These webhooks orchestrate LLM workflows (assignment generation, quiz generation, notes generation, script analysis, mentor chat, submission evaluation). The goal is **total removal of n8n** by:

1. Replacing the workflows with a Python **CrewAI** service exposed via **FastAPI**, hosted on **Railway**.
2. Replacing the raw `fetch(<n8n url>, …)` calls with a single typed client (`src/lib/agentApi.ts`) hitting the new service.
3. Wiring **Supabase JWT auth** and **CORS** so the Vercel frontend can call Railway directly.
4. Cutting the n8n URLs once each crew is verified.

After migration: no n8n dependency, all prompts/agents live in versioned Python code, and long-running flows use a job-poll pattern (already the shape of the script analyzer).

---

## Inventory of n8n call sites (the contract to preserve)

| # | File | Workflow (n8n name) | Webhook ID | Payload | Response shape consumed | Pattern |
|---|---|---|---|---|---|---|
| 1 | `src/pages/ScriptAnalyzer.tsx` (L173-222) | **Script analyser** (active) | `4dd12417-…` | `{ Type, file_url }` | `{ jobId }` then poll `/status/{jobId}` → `{ status, result }`; final `result` is structured analysis | **Async / poll** every 3s up to 20 attempts |
| 2 | `src/pages/StudentAssignments.tsx` (L61, L898-914) | **assignment evaluator** (active) | `6d51e44c-…` | `{ criteria, subtopic, file_url }` | `{ output: <markdown rubric/feedback>, threadId }` parsed by `parseAIFeedback()` (L105-…) | Sync await |
| 3 | `src/pages/CreateAssignment.tsx` (L413) | **Assignment generator** (active) | `6a7c5ac0-…` | `{ subtopic }` | `{ output \| content \| answer }` | Sync await |
| 4 | `src/pages/CreateAssignment.tsx` (L404) | **Assignment generator** (active, second webhook in same workflow) | `e72a35be-…` | `{ content, subtopic, changes }` | same as #3 | Sync await |
| 5 | `src/pages/CreateNotes.tsx` (L711) | **Mentor** (active — workflow is misnamed; serves notes generation) | `6be3ecf4-…` | `{ subtopic }` | `{ output \| content \| notes }` markdown | Sync await |
| 6 | `src/pages/CreateQuiz.tsx` (L501) | **Quiz** (active) | `47ded585-…` | `{ subtopic }` | `{ output: JSON-string with all_questions[] }` | Sync await |
| 7 | `src/pages/AIMentorNew.tsx` (L114-124, L1400-1426) | **Mentor** (active — chat trigger node in same workflow as #5) | `f9303923-…` | `{ chatInput }` | `{ output }` text | Sync await |
| 8 | `src/pages/AIMentorNew.tsx` (L125-134, L1429-1547) | ⚠️ **NOT FOUND in n8n account** | `97354b0e-…` | `{ chatInput }` | `{ output }` array OR `{ all_questions }` OR JSON string | Sync await — see "Open question" below |

**The new service must match these payload + response shapes exactly** so frontend parsing logic (e.g. `parseAIFeedback`, the multi-shape quiz parser at AIMentorNew L1461-1543) keeps working unchanged.

### What we now have locally

The n8n workflow JSON for **7 of 8 webhooks** is committed alongside this doc, under [`docs/n8n-exports/`](./n8n-exports):

- `Script analyser.json` — covers #1
- `assignment evaluator.json` — covers #2
- `Assignment generator.json` — covers #3 + #4 (two webhook nodes in one workflow)
- `Mentor.api.json` — covers #5 + #7 (notes webhook + chat trigger in one workflow)
- `Quiz.json` — covers #6

These were pulled from the n8n Cloud REST API by ID. To re-pull (e.g. if a workflow changes), use any HTTP client with header `X-N8N-API-KEY: <key>`:

```
GET https://vijiteshnaik.app.n8n.cloud/api/v1/workflows           # list
GET https://vijiteshnaik.app.n8n.cloud/api/v1/workflows/{id}      # full JSON
```

This means **the prompts, branching logic, and assistant IDs for 7 of 8 endpoints are captured here** — no further n8n inspection required for those.

### OpenAI assistants in use

These IDs need to be inspected in the OpenAI dashboard (model, system instructions, attached vector store / files). A single `OPENAI_API_KEY` covers all of them:

| Assistant ID | Used by |
|---|---|
| `asst_JAZ3hgBRQzs8i04PMb1rmiJW` | Script analyser (Weekly + Sem branches), Quiz, assignment evaluator |
| `asst_Tpujcej0HQAsB3YaRRo7FIJ2` | Mentor / notes generator (also wired to **Tavily** web search — needs `TAVILY_API_KEY` on Railway) |
| `asst_pfvs8mgkuvnZgsRh9vmj0YRt` | Assignment generator (both generate and revise nodes) |

> **Cruft to ignore:** `Script analyser.json` also contains a disconnected node referencing `asst_TQfhsYUS6QNqkDapnMt3sc6x` ("Gaggar and partner agent" — a legal-firm chatbot leftover). It's not wired into the data flow. Do not port it.

### Branching / non-prompt logic worth noting

- **Script analyser** (`Differentiator` Code node) classifies `body.Type` → `"weekly" | "sem" | "unknown"`:
  - `"assignment"` → weekly prompt
  - `"documentary" | "shortfilm" | "feature film" | "episodic content"` → sem prompt
  - **Bug to fix during migration:** the `Decider` IF node has an empty false branch, so today the webhook silently returns nothing for any non-"assignment" type. Wire the sem branch in the Crew port.
- **Mentor / notes generator** carries a hardcoded **subtopic → reading-materials map** (~50 entries) inside the `Code` node. This must be ported into Python verbatim (use a YAML or JSON resource file under `app/crews/notes_crew/data/reading_materials.yaml`).
- **Mentor chat trigger** uses `@n8n/n8n-nodes-langchain.chatTrigger` (not a regular webhook) and pairs with an AI Agent + memory. CrewAI side: regular `LLM` config + Redis-backed session memory keyed by `sessionId`.

---

## New backend: `screen-scribe-agents` (Python / FastAPI / CrewAI)

### Repo layout

```
screen-scribe-agents/
├── app/
│   ├── main.py                # FastAPI app, CORS, routers
│   ├── config.py              # pydantic-settings env
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── assignments.py # POST /generate, /revise, /evaluate
│   │   │   ├── notes.py       # POST /generate
│   │   │   ├── quizzes.py     # POST /generate
│   │   │   ├── mentor.py      # POST /chat, /quiz
│   │   │   ├── scripts.py     # POST /analyze, GET /analyze/status/{jobId}
│   │   │   └── jobs.py
│   │   └── schemas.py
│   ├── crews/
│   │   ├── assignment_crew/   (crew.py + agents.yaml + tasks.yaml)
│   │   ├── notes_crew/
│   │   ├── quiz_crew/
│   │   ├── mentor_crew/
│   │   ├── script_crew/
│   │   └── evaluator_crew/
│   ├── tools/                 # @tool wrappers (Supabase fetch, file download, …)
│   ├── services/              # supabase_client, storage
│   ├── workers/               # celery_app + tasks (for long jobs)
│   └── core/auth.py           # verify Supabase JWT
├── Procfile                   # web: uvicorn …  worker: celery …
├── pyproject.toml
└── .env.example
```

### Endpoints (designed to mirror the n8n contract 1:1)

| New endpoint | Replaces n8n call # | Body | Returns |
|---|---|---|---|
| `POST /api/assignments/generate` | 3 | `{ subtopic }` | `{ output }` |
| `POST /api/assignments/revise` | 4 | `{ content, subtopic, changes }` | `{ output }` |
| `POST /api/assignments/evaluate` | 2 | `{ criteria, subtopic, file_url }` | `{ output, threadId }` |
| `POST /api/notes/generate` | 5 | `{ subtopic }` | `{ output }` |
| `POST /api/quizzes/generate` | 6 | `{ subtopic }` | `{ output: "<json string with all_questions>" }` |
| `POST /api/mentor/chat` | 7 | `{ chatInput, sessionId? }` | `{ output }` |
| `POST /api/mentor/quiz` | 8 | `{ chatInput }` | `{ output }` (matches existing multi-shape parser) |
| `POST /api/scripts/analyze` | 1 | `{ Type, file_url }` | `{ jobId }` |
| `GET /api/scripts/analyze/status/{jobId}` | 1 | – | `{ status: pending\|running\|completed\|error, result?, error? }` |

Long crew runs (script analysis, evaluation) enqueue to Celery + Redis; short ones (subtopic-only generation) run inline. Auth = Supabase JWT verified using `SUPABASE_JWT_SECRET`. CORS allows `https://*.vercel.app` + the prod domain + `http://localhost:8080` (Vite dev port from `vite.config.ts`).

### Hosting on Railway
- Two services in one project: `web` (uvicorn) + `worker` (celery) + Redis add-on.
- Env: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`, `REDIS_URL`, `ALLOWED_ORIGINS`.

---

## Frontend changes (screen-scribe-pilot)

### 1. New shared client — `src/lib/agentApi.ts` (NEW file)

Centralizes base URL, auth header injection (Supabase JWT via `supabase.auth.getSession()` — already used in `src/hooks/useAuth.tsx:98`), and error toasts (use existing `sonner` via `src/hooks/use-toast.ts`).

Exports:
- `generateAssignment({ subtopic })`
- `reviseAssignment({ content, subtopic, changes })`
- `evaluateSubmission({ criteria, subtopic, file_url })`
- `generateNotes({ subtopic })`
- `generateQuiz({ subtopic })`
- `mentorChat({ chatInput, sessionId? })`
- `mentorQuiz({ chatInput })`
- `startScriptAnalysis({ Type, file_url })` → `{ jobId }`
- `pollScriptAnalysis(jobId)` (encapsulates the 20-attempt × 3s loop currently inline in `ScriptAnalyzer.tsx:173-191`)

Each function returns the same shape the calling page already expects (`{ output }` etc.) so per-page diffs stay tiny.

### 2. New env var

Add `VITE_AGENT_API_URL` to:
- `.env.local` (dev → `http://localhost:8000`)
- Vercel project env (prod → `https://<railway-host>`)

This is the project's first `VITE_*` var (the infra audit confirmed none exist today), so also add `.env.example` and document in README.

### 3. Per-file edits — pure URL/import swap, no logic changes

| File | Change |
|---|---|
| `src/pages/ScriptAnalyzer.tsx` | Delete `N8N_SCRIPT_ANALYZER_ENDPOINT` (L51-ish); replace `triggerScriptAnalysis` body to call `startScriptAnalysis` + `pollScriptAnalysis` from `agentApi.ts`. Remove inline `pollN8nJobResult` (L173-191) — moved to client. |
| `src/pages/StudentAssignments.tsx` | Delete `N8N_ASSIGNMENT_EVALUATOR_ENDPOINT` (L61); replace `callN8nAgent` (L898-914) with `evaluateSubmission`. **Do NOT touch `parseAIFeedback`** — backend returns the same `{ output }` markdown shape it already parses. |
| `src/pages/CreateAssignment.tsx` | Replace the two `fetch` calls in `callAssignmentAgent` (L404, L413) with `generateAssignment` / `reviseAssignment`. |
| `src/pages/CreateNotes.tsx` | Replace `fetch` at L711 with `generateNotes`. |
| `src/pages/CreateQuiz.tsx` | Replace `fetch` at L501 with `generateQuiz`. Quiz parser (L499-587) stays. |
| `src/pages/AIMentorNew.tsx` | Delete `AI_MENTOR_AGENT_CONFIG` (L114-135). Replace `callMentorAgent` (L1414) with `mentorChat`; replace `callQuizGenerationTool` (L1444) with `mentorQuiz`. The multi-shape parser (L1461-1543) is preserved. |

No other files in `src/` reference n8n — confirmed by grep across the whole tree.

### 4. Optional: introduce React Query

`QueryClient` is already provided in `App.tsx:42` but unused. Wrapping the new client functions in `useMutation` is a nice-to-have (auto-loading states, retries) but **not part of the migration**; current per-page `useState` loading flags keep working.

---

## Phased execution

The 8 endpoints are independent — migrate one at a time and verify before moving on. **Phase A covers the 7 endpoints whose n8n logic is already captured in `docs/n8n-exports/`. Phase B handles the missing mentor-quiz endpoint after the rest are live.**

### Phase A — the 7 we have

1. **Set up the new repo** (`screen-scribe-agents`), deploy a `/health` endpoint to Railway, configure CORS, confirm a curl from the laptop and a `fetch` from a Vercel preview both return 200. Inspect the 3 OpenAI assistants listed above; capture their model + system instructions + attached files. Spin up `OPENAI_API_KEY` and `TAVILY_API_KEY` in Railway env.
2. **Frontend scaffolding**: add `VITE_AGENT_API_URL`, create `src/lib/agentApi.ts` with just `health()` first, prove end-to-end auth round-trip.
3. **Migrate the simplest crews first** (single `subtopic` in, text out), in order:
   1. **Notes** (#5) — port `Mentor.api.json` notes branch. Includes the hardcoded reading-materials map and the Tavily web-search tool. Asst `asst_Tpujcej0HQAsB3YaRRo7FIJ2`.
   2. **Assignment generate** (#3) — port `Assignment generator.json` (path `6a7c5ac0-…`). Asst `asst_pfvs8mgkuvnZgsRh9vmj0YRt`.
   3. **Assignment revise** (#4) — same workflow, second node (path `e72a35be-…`).
   4. **Quiz** (#6) — port `Quiz.json`. Asst `asst_JAZ3hgBRQzs8i04PMb1rmiJW`. Output must be a JSON string with `all_questions[]`.
4. **Mentor chat** (#7) — port the chat-trigger half of `Mentor.api.json`. CrewAI `LLM` + Redis-backed session memory keyed by `sessionId`.
5. **Submission evaluation** (#2, `/api/assignments/evaluate`) — port `assignment evaluator.json`. Pin the prompt so the rubric markdown shape matches `parseAIFeedback` regexes (`## 📊 Rubric-Based Scoring`, `**Total**`, `Strengths`, `Areas for Improvement`, `Recommendations`, `Academic Integrity`, `Status`). Asst `asst_JAZ3hgBRQzs8i04PMb1rmiJW`.
6. **Script analyzer** (#1) — port `Script analyser.json`. Most operationally complex (job + poll + Celery worker). Two task variants (weekly / sem) sharing the same agent. **Fix the empty sem branch** during the port. Keep the client's 20×3s polling cadence. Asst `asst_JAZ3hgBRQzs8i04PMb1rmiJW`.
7. **Cut n8n for the 7**: once these are live for a few days, delete the corresponding n8n constants in the frontend, and disable the 5 source workflows in n8n.

### Phase B — mentor quiz (#8), deferred

⚠️ **Webhook `97354b0e-7edd-46f3-b80f-49fbd3e0150c` (the second AIMentorNew call site) does not exist in the n8n account.** A full scan of all 98 workflows via the n8n REST API found no node carrying this path. The frontend currently calls a URL that is almost certainly returning 404 in production.

Do **not** block Phase A on this. After Phase A is live, do this:

1. **Confirm current behavior in production.** Open `/ai-mentor` in DevTools → Network tab and exercise whatever feature triggers webhook #8 (Semester 2 mentor / in-mentor quiz). If it 404s, the feature has been broken for some time and no users depend on the response.
2. **Decide intent.** Read `AIMentorNew.tsx:125-134, 1429-1547` and the multi-shape parser to determine what response shape was expected. Likely a quiz JSON similar to #6 but in chat-trigger style.
3. **Build it fresh in CrewAI.** No n8n workflow exists to clone — design the prompt from the parser's expectations and the surrounding mentor-chat tone. Reuse the mentor-chat crew skeleton; swap the system prompt to one that produces the expected quiz shape.
4. **Add the route**: `POST /api/mentor/quiz` (already in the endpoint table below). Wire `mentorQuiz()` in `agentApi.ts`.
5. **If the production 404 confirms the feature is dead**, consider just removing call site #8 from `AIMentorNew.tsx` instead of reimplementing — but only after product confirmation.

---

## Critical files to modify (frontend only — backend is a new repo)

- `src/pages/ScriptAnalyzer.tsx` — L51, L173-222
- `src/pages/StudentAssignments.tsx` — L61, L898-914 (leave parser at L105-… alone)
- `src/pages/CreateAssignment.tsx` — L404, L413, surrounding `callAssignmentAgent`
- `src/pages/CreateNotes.tsx` — L711
- `src/pages/CreateQuiz.tsx` — L501
- `src/pages/AIMentorNew.tsx` — L114-135, L1414, L1444
- `src/lib/agentApi.ts` — NEW
- `.env.example`, `.env.local` — add `VITE_AGENT_API_URL`
- `vercel.json` — no change (SPA rewrite is fine; no proxying needed)

Reuse existing utilities (do not re-create):
- `supabase` client — `src/integrations/supabase/client.ts`
- Auth/session — `src/hooks/useAuth.tsx`
- Toast — `src/hooks/use-toast.ts` (sonner)
- Supabase storage upload helper — already in `ScriptAnalyzer.tsx:224-…` (`uploadFileToSupabase`)

---

## Verification

For each endpoint, after wiring:

1. `npm run dev` (Vite on port 8080) and exercise the affected page end-to-end:
   - **Notes**: open `/teacher/create-notes`, generate notes for a known subtopic, confirm the rendered markdown matches output from the old n8n call.
   - **Assignment generate/revise**: `/teacher/create-assignment` — generate, then request a revision; verify both calls return content and that revision actually changes the prior content.
   - **Quiz**: `/teacher/create-quiz` — generate; verify the parsed `all_questions` array renders correctly (4 options each, correct answer present).
   - **Mentor**: `/ai-mentor` — multi-turn chat for both Semester 1 and Semester 2 selectors; trigger an in-mentor quiz and verify the multi-shape parser still works.
   - **Submission evaluation**: `/student/assignments` — submit a sample file, confirm rubric markdown parses into the existing UI structure (Score, Overall Grade, Strengths, Areas for Improvement).
   - **Script analyzer**: `/script-analyzer` — upload PDF/DOCX, watch poll loop tick to completion; confirm result renders.
2. Network tab confirms `https://<railway-host>/api/...` is hit and `vijiteshnaik.app.n8n.cloud` is **never** hit.
3. Backend: `pytest` covers each route with a mocked LLM and a smoke test of one real crew run per crew.
4. Final regression: a fresh Vercel preview deploy with `VITE_AGENT_API_URL` set; click through each of the 6 affected pages.
5. Final cleanup pass: `grep -ri "n8n\|vijiteshnaik" src/` returns zero matches before merging.

---

## Gaps surfaced after a second pass (must address before implementation)

### A. Supabase Edge Function shadow path
`supabase/functions/evaluate-submission/index.ts` exists and is a **mock** evaluator (returns hardcoded `mockEvaluation` and writes to `submissions.ai_evaluation` / `submissions.ai_feedback`). The current frontend (`StudentAssignments.tsx`) bypasses it and calls n8n directly, so this function appears unused. Confirm with the team, then either:
- **Delete** the edge function (preferred — dead code), or
- **Repurpose** it as a thin proxy to `POST /api/assignments/evaluate` on Railway.

Either way, decide before flipping the eval flow so we don't leave two server-side evaluation paths writing to the same columns.

### B. Capture the existing n8n response shapes before turning workflows off
The plan promises "match payload + response shapes exactly," but two flows write the response into the database, so we need *concrete samples* — not just our reading of the parser code:

- **`script_analyses.analysis_result` (JSONB)** — `ScriptAnalyzer.tsx:347, 381` writes the raw n8n `result` field into the table, and it is later consumed by `TeacherScriptSubmissions.tsx`, `TeacherDashboard.tsx`, `StudentDashboard.tsx`. CrewAI must reproduce the same JSON keys.
- **`submissions.ai_evaluation` / `ai_feedback`** — `StudentAssignments.tsx` writes the parsed evaluation (rubric markdown w/ `## 📊 Rubric-Based Scoring` header, `**Total**` row in the markdown table, `Strengths` / `Areas for Improvement` / `Recommendations` / `Academic Integrity` / `Status` sections — see `parseAIFeedback` regexes at L160-184). The CrewAI prompt must pin this exact markdown shape.

**Status:** the n8n workflow definitions (prompts, branching, model config) are already exported under `docs/n8n-exports/` — see "What we now have locally" above. Still TODO before flipping each crew live: hit each n8n webhook once with a realistic payload (Postman/curl) and save the response as a golden fixture in `docs/n8n-samples/<workflow>.json`. Backend `pytest` cases assert against these fixtures.

### C. Vapi voice assistant (`/old-ai-mentor`) — out of scope, but verify
`src/pages/AIMentor.tsx` uses the Vapi web SDK with hardcoded keys (assistant `0b36eadb-ae94-4a97-b1fb-90b7128f3630`, public key `33f65907-…`). The frontend doesn't hit n8n in this file, **but** Vapi assistants can have server-side tools that call webhooks — confirm in the Vapi dashboard whether this assistant is wired to any `vijiteshnaik.app.n8n.cloud` URL. If yes, those need to be repointed at the new Railway service too. If no, ignore.

### D. Glossary import script
`package.json` declares `"import:glossary": "node scripts/import-glossary.mjs"`. Quickly inspect to confirm it doesn't hit n8n; it likely just reads CSV/JSON into Supabase, in which case it's untouched by this migration. Worth a 30-second skim.

### E. Hardcoded secrets currently in source
Out of scope of this migration but worth flagging while we're touching this surface: the Supabase publishable key (`src/integrations/supabase/client.ts`) and Vapi public key (`src/pages/AIMentor.tsx`) are hardcoded. The publishable/anon keys are designed to be public so this is not a vulnerability, but moving them to `VITE_*` env vars at the same time we add `VITE_AGENT_API_URL` keeps config consistent.

### F. This plan file is publicly served
~~`public/migratetocrew.md` will be served at `https://<vercel-host>/migratetocrew.md` once deployed.~~ **Resolved:** moved to `screen-scribe-agents/docs/MIGRATE.md` (this file). The frontend repo no longer contains it.

### G. Backend persistence model — decide now
The current setup has the **frontend** writing crew results to Supabase (script_analyses, submissions). After migration, two options:
1. **Keep as-is**: CrewAI returns the result in the HTTP response, frontend writes it to Supabase. Simplest diff. ✅ Recommended.
2. **Move writes server-side**: CrewAI worker writes to Supabase using service-role key, frontend just polls. Cleaner for long jobs but requires duplicating Supabase schema knowledge in Python.

Plan defaults to option 1; revisit only if the script analyzer's poll loop becomes a UX problem.
