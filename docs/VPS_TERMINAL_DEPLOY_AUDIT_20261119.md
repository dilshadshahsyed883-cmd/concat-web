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


## New finding: authoritative Scene candidate runtime (read-only)

User-supplied VPS terminal probe inspected the active `vps1-scene-candidate.service` unit and the runtime's effective `WEB_DATA_DIR` (without printing credentials). It reported:

```text
SCENE_PID_RUNNING= True
SCENE_APP_PATH= /srv/fresh-website/current/scene-builder/part01
SSO_ISSUER_FILE= False
SCENE_DB_PATH= /var/lib/fresh-website/scene-builder/web/web.sqlite3
SCENE_DB_EXISTS= True
USERS_TABLE= True
CONCAT_SSO_TABLE= False
VPS_CHANGES=NONE
```

**Correct live Scene DB:** `/var/lib/fresh-website/scene-builder/web/web.sqlite3`.  
**Important blocker:** the currently running candidate code tree does not contain `concat_sso_issuer.py`, and this live database has no `concat_sso_sessions` table. Hence the Scene issuer integration is **not deployed/initialized in the inspected candidate**. Upstream VPS1 SSO issuer PR #773 is merged in source, but a source merge is not proof of live service deployment. No safe route exists to bypass this blocker in Concat Web.

### Impact and next steps

- **Do not start or expose Concat Web yet;** login must remain fail-closed.
- Resolve the upstream SSO release through the **VPS1 repository's separate controlled deployment** after verifying it is ready. Preserve VPS1 production; do not copy issuer Python modules into the live host manually, run schema-changing SQL manually, or turn off SSO/security gates.
- Once upstream is live, confirm that `concat_sso_issuer.py` is present in the active code release and the authoritative Scene DB contains `concat_sso_sessions`. Then confirm schema and read-only SQLite WAL access from `concatweb`.
- Provision the private Concat environment only after aligning the approved cross-app signing secret, runtime path, and isolated settings. Run Concat preflight (without deployment) before any loopback release.
- The Ubuntu restart/upgrade banner is unrelated to this verification; don't reboot/upgrade as part of this work.

This finding **supersedes the earlier guessed DB path** and clarifies why the scan of 12 transaction backup databases was not diagnostic of the live issuer.
