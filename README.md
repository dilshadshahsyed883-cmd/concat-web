# Concat Web

Independent FastAPI + Jinja web application for the existing VPS_1 server, **not** a modification of the current VPS_1 website. Uses existing first-party VPS_1 implementations under `reused/` with COPY → ADAPT → VERIFY.

## Local foundation test

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m unittest discover -s tests -p 'test_foundation.py' -v
python run.py
# GET http://127.0.0.1:18873/healthz
```

By design `/dashboard`, `/concat/...`, `/concat-uploader/...` and `/admin` return **401 until verified identity is connected by Agent 5**. No exposed temporary login. For offline tests, the resolver is injected directly into the in-process ASGI test app.

Exactly three top-level sidebar entries: Dashboard / Concat Studio (Concat: Production, Media, GPU Config; Concat Uploader: Sheets Sync, Channels, Upload Engine, Queue) / Admin. Admin is separately permission-gated.

## Parallel integration
See `docs/AGENT_HANDOFF.md` for module ownership, APIs and source entrypoints; `docs/REUSE_MANIFEST.md` for copied source provenance and security limitations; `deploy/RELEASE_GATES.md` for guarded deployment readiness. The source copies are integration inputs, not yet exposed business endpoints. Agents 2–5 adapt and verify these modules. No production service, DNS, TLS, database, worker image or EXE is touched.
