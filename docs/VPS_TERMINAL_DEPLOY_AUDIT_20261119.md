# Concat Web: manual VPS terminal deployment audit — 2026-11-19

**Dedicated work branch:** `ops/terminal-deployment-audit-20261119`  
**Source repository:** `dilshadshahsyed883-cmd/concat-web`  
**Deployment policy:** All changes committed to a feature/ops branch and reviewed in a PR. Production release uses a tested SHA from protected `main` and a manual VPS terminal operation; GitHub Actions automatic deployment is not desired. The existing VPS_1 website, Nginx routes, Drive Bridge, OAuth, Salad and data remain unchanged.

This is a record of **user-supplied terminal output**, not independently executed VPS inspection.

## Read-only baseline before bootstrap

| Check | Result |
|---|---|
| Nginx config | PASS |
| Port 18873 | FREE |
| `concatweb` Linux user | MISSING |
| `concat-web.service` | MISSING |
| `/usr/local/sbin/concat-web-deploy` | MISSING |
| `/etc/concat-web/concat-web.env` | MISSING |

## Bootstrap successful (service NOT started)

Pinned source commit: `0a4595995308ce147eac5bac7f25ad270d7bd17a`.

The operator downloaded two existing deployment files from this exact commit:
- `deploy/guarded-release.sh`; Git blob SHA `9eb546b7e27ea579fca2196878ff339af9f71a25`
- `deploy/concat-web.service`; Git blob SHA `6dade198aac2b555307511d7f2ee6d00ee86b723`

Both `git hash-object` checks passed. Shell output:

```text
SOURCE_VERIFICATION=PASS
CONCAT_BOOTSTRAP=PASS
CONCAT_SERVICE=INSTALLED_NOT_STARTED
SCENE_SSO_SCHEMA=DB_NOT_FOUND_AT_EXPECTED_PATH
```

Successful script execution means `concatweb`, private Concat storage paths and release directory, root-owned deployment helper and independent systemd unit were set up. The script did NOT create the private environment file, run a release, start Concat, or modify Nginx.

The initially guessed Scene DB path `/opt/scene-builder-web/data/web.sqlite3` does not exist. This does **not** prove Scene SSO tables are missing elsewhere.

## Targeted Scene service and database discovery (read-only)

Reported active systemd services:
- `vps1-scene-candidate.service`, running; `WorkingDirectory=/srv/fresh-website/current/scene-builder/part01`.
- `vps1-scene-production-worker.service`, running.
- `vps1-scene-worker-admission.service`, running.
- Other VPS1 production LUM/song/short services are running.

An explicit SQLite scanner searched under `/opt`, `/srv`, and `/var/lib`, skipping `.git`, `node_modules`, virtualenvs and Concat own storage. It inspected 90 candidate DBs and **stopped after finding 12 matching databases**. The 12 results are all under historical `/srv/fresh-website/transactions/.../backup/` or `.../sqlite-backup/` paths. Each has a `users` table and none has `concat_sso_sessions`. Therefore the scan is **not an exhaustive survey** and cannot be used to conclude that the **live** Scene database or SSO schema is absent.

Important: Do not select a transaction backup SQLite file as the SSO authority. Determine the database path from the active Scene service's actual configuration and verify the schema against that active DB **read-only**, as `concatweb`. Do not show env values, tokens, keys, or SQL row data in terminal screenshots or GitHub.

## VPS OS notice

The VPS login banner reported pending package/security updates, Ubuntu 26.04.1 LTS upgrade available, and a required restart. These are maintenance notices, **not evidence** of a Concat application failure. No blanket `apt upgrade`, `do-release-upgrade`, service restart, or server reboot should be mixed into Concat bootstrap.

## Release blockers

1. Determine the actual live Scene users DB path, then verify `users(username,is_active,is_admin)` and `concat_sso_sessions(sid_hash,username_key,expires_at,revoked_at)` read-only, including access by `concatweb`.
2. Verify upstream Scene SSO issuer is **deployed live**, with exact signing key and session revocation support; code merged in GitHub alone is insufficient.
3. Create root-owned `0600` `/etc/concat-web/concat-web.env` with the **already-approved** cross-app SSO key and app secrets, owner-scoped persistent storage and HTTPS origins. Never save secrets to repo/chat/logs.
4. Run the existing **installed** `/usr/local/sbin/concat-web-deploy preflight <verified-main-SHA>`. It fails closed when prerequisites are missing.
5. Only after preflight, CI and live SSO acceptance: package the exact tested `main` SHA, upload via a secure terminal channel and invoke the installed guarded helper to stage the independent loopback service. Public Nginx route/TLS cutover is a **separate** guarded step.
6. Verify Concat-only /healthz, denial of anonymous private routes, two-owner/admin SSO and revocation, and a controlled GPU-to-verified-MP4-to-uploader acceptance test. Preserve independent rollback and prior releases.

**Current state:** bootstrap complete; no Concat release or public activation; live SSO DB path unresolved; private environment unprovisioned; existing VPS1 production preserved as far as operator-reported steps show.
