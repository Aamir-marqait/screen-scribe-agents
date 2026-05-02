from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def root() -> str:
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>screen-scribe-agents</title>
<style>
  body { font-family: system-ui, sans-serif; display: grid; place-items: center; height: 100vh; margin: 0; background: #0b0b0c; color: #e7e7e8; }
  .card { text-align: center; }
  h1 { font-size: 1.6rem; margin: 0 0 0.5rem; }
  p { margin: 0.25rem 0; opacity: 0.75; }
  a { color: #7aa7ff; }
  .dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; background: #2ecc71; margin-right: 0.5rem; vertical-align: middle; box-shadow: 0 0 12px #2ecc71; }
</style>
</head>
<body>
  <div class="card">
    <h1><span class="dot"></span>screen-scribe-agents is running</h1>
    <p>API docs: <a href="/docs">/docs</a> &middot; Health: <a href="/health">/health</a></p>
  </div>
</body>
</html>"""


@router.get("/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "screen-scribe-agents"}
