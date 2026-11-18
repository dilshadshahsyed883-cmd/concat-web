# Concat Uploader — in-process, owner-scoped reuse

This module shows the real, copied VPS_1 Copyright Uploader (including PR
#770) in a same-origin frame under the canonical Concat Web sidebar, rather
than drawing placeholder tabs. Only
\`/concat-uploader/**\` is exposed. Public entrypoints are Sheets Sync,
Channels (Channel Manager / Accounts & Tokens), Upload Engine, and Queue.

## Fail-closed bootstrap

Agent 5 installs the **verified** Scene-session resolver on
\`app.state.identity_resolver\`. This module never accepts client-supplied
username, role, or app-grant headers. The router verifies a current, active,
Concat-granted Principal *before* any uploader import or request. The adapter
then invokes the copied FastAPI app **in process**, forwarding the original
request body and cookie while replacing authentication headers with the
verified identity. Legacy administrative, Auto V6, setup, global Web OAuth and global settings
routes are not exposed, even for Concat Web administrators.

The following deployment settings must be supplied by the integrator and
cannot be committed as credentials:

- \`CONCAT_UPLOADER_ENABLED=1\`
- \`LUM_DATA_DIR=/var/lib/concat-web/uploader\` (dedicated, persistent, private)
- \`LUM_SESSION_SECRET=<independently-generated-at-least-32-char-secret>\`
- \`CONCAT_CLOUD_RENDER_ROOT=<path-to-owner-verified-cloud-render-data>\`
- \`CONCAT_PUBLIC_ORIGIN=https://app.scenebuilder.online\` for legacy Copy
  Video Links, or the verified Concat Web origin when its own Media IDs are
  implemented.

The adapter enforces \`LUM_ENGINE_INSTANCE=concat\`,
\`LUM_BASE_PATH=/concat-uploader\`, \`LUM_SUITE_AUTH=1\`,
\`LUM_COOKIE_SECURE=1\`, and \`CONCAT_WEB_IN_PROCESS=1\`. Conflicting values are
rejected; OAuth, worker, staging, queues and SQLite remain in the dedicated
\`LUM_DATA_DIR\`. Do not point these paths at Song or Copyright Uploader.

Install copied uploader's actual Python dependencies in the deployment image
as well as Concat Web's dependencies:

\`\`\`sh
python -m pip install -e '.[test]'
python -m pip install -r reused/uploader/part01/requirements.txt
python -m unittest discover -s app/modules/uploader/tests -p 'test_*.py' -v
\`\`\`

Worker startup happens only after a verified request and successful backend
initialization. ASGI shutdown stops the worker. Queues start paused and require
manual Start Queue, even after a restart; YouTube uploads preserve resumability,
verified cleanup, owner+channel duplicate detection and per-channel OAuth.

**Integration gates remain:** Agent 2 must provide an owner-attributed Cloud
Render \`files.owner_username\` schema and verified local MP4 handoff. Ownerless
legacy rows and arbitrary HTTP URLs are denied. Agent 5 must provide verified
session resolution and CSRF/revocation assurance. No live YouTube upload or
production connection is tested by this feature PR.
