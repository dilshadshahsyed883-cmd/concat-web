# Concat Web

Independent FastAPI application for the existing VPS_1 host. The original Scene website is unchanged. Integrated PR #3 (Uploader), #4 (Concat Studio), #5 (Dashboard), and #6 (Admin/security) are copied from their verified source trees.

## Routes and source boundaries

The sidebar has exactly three top-level sections: Dashboard, Concat Studio, and Admin. Concat Studio contains Production, Media, GPU Config, and Copy Video Link. Concat Uploader exposes Sheets Sync, Channels, Upload Engine and Queue by calling the copied uploader in process after verified authentication.

Dashboard uses read-only owner-scoped queries against the real Cloud Render and uploader SQLite stores, not mock counters. The personal deployment uses explicit `CONCAT_AUTH_MODE=local` with one configured, independently authenticated administrator, private revocable sessions, secure CSRF protection and login rate limiting. Legacy Scene SSO remains available for compatibility tests, but is **not required** for the personal release.

Concat stores each user's videos and jobs in a private per-owner SQLite directory under $CONCAT_WEB_DATA_ROOT/owners/sha256(canonical_username). The copied uploader's verified media admission checks the same owner-specific directory and copies a SHA-verified ready MP4 to private staging. The legacy global single-database source is supported only when its owner_username field matches the authenticated owner; ownerless data is never migrated.

## Offline verification and wheel

    python -m pip install -e '.[test]'
    python -m compileall -q app reused run.py
    python -m unittest discover -s tests -p 'test_foundation.py' -v
    python -m unittest discover -s tests -p 'test_reused_*.py' -v
    python -m unittest app.modules.concat.test_routes -v
    python -m unittest discover -s app/modules/uploader/tests -p 'test_*.py' -v
    python -m unittest discover -s tests -p 'test_admin_security.py' -v
    python -m unittest discover -s tests -p 'test_local_admin.py' -v
    python -m pip wheel --no-deps --wheel-dir /tmp/concat-web-wheel .

Fixtures verify a signed-in receiver's simulated output, verified MP4, copied persistent queue, dashboard, owner isolation, CSRF, and legacy quarantine. Tests do not publish live YouTube videos or invoke Salad GPU.

## Release status

Local-admin source is under PR review and not yet deployed. No merge or deployment is authorized by this change. The GitHub release workflow only validates source; production deployment is manual VPS terminal with SHA pinning, backups and rollback. Real OAuth/YouTube/Salad acceptance remains a separate live check. See deploy/RELEASE_GATES.md for the revised checklist and docs/VPS_TERMINAL_DEPLOY_AUDIT_20261119.md for historical SSO findings. Main, VPS_1 production services, Nginx and GPU images remain unchanged.
