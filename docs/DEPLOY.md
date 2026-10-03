# Hosted demo
**API** (any container host: Render, Fly.io, Railway, Cloud Run):

    docker build -t errorlens-api .
    docker run -p 8000:8000 -e ERRORLENS_CORS=https://YOUR-WEB.vercel.app errorlens-api

Optional: `-e ANTHROPIC_API_KEY=...` enables *Sanitized AI* mode (the key stays on the server; only redacted structured facts are sent).
Leave `ERRORLENS_ALLOW_REPO_PATH` unset on any public server (it lets requests read server folders).

**Web** (Vercel): import the `web/` folder, set `NEXT_PUBLIC_ERRORLENS_API=https://YOUR-API-HOST`, deploy.

On a public demo everyone shares one history table. The API stores only fingerprints + summaries, but add
per-session scoping (or call analyze with `save=false`) before inviting real users.
