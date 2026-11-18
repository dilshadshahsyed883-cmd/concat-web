# Concat Web production release — staged and guarded

This repository has a **manual** GitHub Actions workflow at
`.github/workflows/deploy.yml`. It is deliberately not a push-to-main auto-deploy
until real Scene SSO, private storage and the live GPU/upload handoff have been
accepted. All releases use an exact reviewed `concat-web/main` SHA.

## Host prerequisites (inspect before provisioning)

- Dedicated `concatweb` Linux user; `/srv/concat-web/releases` root-owned,
  `/var/lib/concat-web` owned by `concatweb`, mode 0700. Never reuse VPS_1
  app state, uploader databases, credentials, worker state or Drive Bridge folders.
- Ubuntu 24.04 Python 3.12, `python3-venv`, curl, flock, Nginx, systemd.
- Root-owned `/etc/concat-web/concat-web.env`, mode 0640 or stricter, readable by
  `concatweb` through a dedicated group, never committed. Start with
  `.env.example`. Exact independent `CONCAT_SCENE_SSO_SECRET` (>=32 random
  bytes) must also be installed in the live Scene process; it must not equal
  its session secret. Use a separately generated `LUM_SESSION_SECRET`.
- The `CONCAT_SCENE_USERS_DB` must be the **existing live** Scene SQLite
  database. Grant the `concatweb` identity read-only access to users and
  `concat_sso_sessions`, including SQLite WAL/SHM visibility. The deployment
  script tests actual reads as `concatweb` and refuses a writable database.
  Do not copy/modify Scene database or credentials.
- Install `deploy/concat-web.service.example` as the dedicated unit after
  auditing it, with these two release-scoped corrections:
  `ExecStart=/srv/concat-web/current/.venv/bin/python /srv/concat-web/current/run.py`
  and `WorkingDirectory=/srv/concat-web/current`. `User=concatweb`,
  `EnvironmentFile=/etc/concat-web/concat-web.env`, loopback
  `127.0.0.1:18873`, and `ReadWritePaths=/var/lib/concat-web` are mandatory.
  Do not install or alter any VPS_1 unit.
- Maintain the existing separate TLS virtual host for
  `concat.scenebuilder.online`. **Do not proxy public traffic** to the new
  Concat unit until an authenticated SSO acceptance and rollback rehearsal
  have passed. No deployment workflow edits Nginx.

## GitHub release environment

Create protected environment `concat-web-production` with required reviewers,
then configure these secret values there, not in source:

| Secret | Purpose |
| --- | --- |
| `CONCAT_VPS_HOST` | Approved VPS SSH host/IP |
| `CONCAT_VPS_USER` | Restricted SSH deploy login with explicit `sudo -n` for the isolated script |
| `CONCAT_VPS_SSH_PRIVATE_KEY` | Dedicated deploy SSH private key |
| `CONCAT_VPS_KNOWN_HOSTS` | Independently verified **pinned** SSH host key; never automatic `ssh-keyscan` trust |

Set repo variable `CONCAT_WEB_DEPLOY_ENABLED=true` **only after** host/SOO
readiness review. The default (unset) value prevents any release job from
running. A reviewed operator may manually dispatch the workflow from
`main`, supplying the exact current `main` SHA. There is no silent fallback
to another SHA, runner or host, no deployment from a branch, and no unsafe
SSH host-key bypass.

The workflow runs full focused tests, compiles, creates a Python wheelhouse,
then sends an archive through pinned SSH. `guarded-release.sh` checks the
service identity, root-owned configuration, isolated paths, exact HTTPS
origins, secret presence, read-only live Scene DB and Nginx syntax **before**
touching the Concat unit. It installs a SHA-specific virtualenv, switches the
Concat-only symlink, restarts that unit, tests loopback health and rejects
anonymous access. Failure restores only the prior Concat symlink/unit.
Existing Scene services, Nginx routing, Salad, OAuth and Drive Bridge
remain untouched. Persistent queues are never erased.

## Mandatory live acceptance before public cutover

1. Confirm the merged Scene issuer is **actually deployed**, with the exact
   issuer schema and shared signing key; a GitHub merge alone is not rollout.
2. Check Scene's `/concat-sso/authorize` and Concat's
   `/auth/scene/callback` do not log ticket, state or Location values.
   Prefer sensitive-path access-log suppression or path-only log format.
   Verify production Host and Origin forwarding, TLS, `__Host-` cookies.
3. Real HTTPS browser tests: two users + admin; login, grant, revocation,
   logout propagation, replay, forged callback, CSRF, role demotion, and
   cross-user/legacy-ownerless media, job, source and upload denial.
4. Controlled non-production media/credentials: Drive Bridge private
   source → Salad GPU receiver → checksum-verified MP4 → Copy Video Link
   → owner-scoped Concat Uploader queue. Real YouTube OAuth and publish
   receipt are a separate explicit test, not implied by an offline fixture.
5. Snapshot service/release and SQLite consistently before exposure.
   Review the existing `concat.scenebuilder.online` Nginx TLS site for
   collisions, then proxy **only that site** to `127.0.0.1:18873`.
   Confirm `nginx -t`, `/healthz`, real authenticated routing and
   `https://app.scenebuilder.online` health. On failure restore the
   previous Concat Nginx config and Concat-only release symlink.

**Current limitation:** A connected VPS SSH execution tool and verified
production environment settings are not available to this GitHub-only
workflow authoring task. Committing this gated workflow is not an actual VPS
deployment or proof of live SSO/YouTube/Salad acceptance.
