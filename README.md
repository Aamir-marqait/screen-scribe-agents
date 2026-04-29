# screen-scribe-agents

CrewAI + FastAPI service replacing the n8n workflows for the [screen-scribe-pilot](https://github.com/Aamir-marqait/screen-scribe-pilot) frontend.

## Status

Phase A scaffold. Initial reference crew implemented: **Notes generator** (`POST /api/notes/generate`).

The 8 endpoints we are migrating off n8n:

| # | Endpoint | Status |
|---|---|---|
| 1 | `POST /api/scripts/analyze` (+ status poll) | TODO |
| 2 | `POST /api/assignments/evaluate` | TODO |
| 3 | `POST /api/assignments/generate` | TODO |
| 4 | `POST /api/assignments/revise` | TODO |
| 5 | `POST /api/notes/generate` | ✅ scaffolded |
| 6 | `POST /api/quizzes/generate` | TODO |
| 7 | `POST /api/mentor/chat` | TODO |
| 8 | `POST /api/mentor/quiz` | ⚠️ deferred — original n8n workflow not found, see `migratetocrew.md` |

## Local dev

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env         # fill in OPENAI_API_KEY, etc.
uvicorn app.main:app --reload --port 8000
```

Then:

```bash
curl http://localhost:8000/health
```

## Layout

```
app/
  main.py              FastAPI app, CORS, router registration
  config.py            pydantic-settings (env)
  api/
    schemas.py         shared request/response models
    routes/            one router per resource (notes, assignments, quizzes, mentor, scripts)
  core/
    auth.py            Supabase JWT verification dependency
  crews/               one CrewAI crew per former n8n workflow
    notes_crew/        generate study notes from a subtopic
  services/            external clients (Supabase, etc.)
  tools/               @tool wrappers (Tavily web search, file fetch, etc.)
tests/
```

## Auth

All `/api/*` routes require a valid Supabase JWT in the `Authorization: Bearer …` header. The frontend sends the same token it gets from `supabase.auth.getSession()`.

## Deployment

Railway, with `Procfile` + `railway.json`. Set env vars from `.env.example` in the Railway service.

## Migration context

See [`docs/MIGRATE.md`](./docs/MIGRATE.md) for the full migration plan and [`docs/n8n-exports/`](./docs/n8n-exports) for the original n8n workflow definitions (prompts, branching, model config).
