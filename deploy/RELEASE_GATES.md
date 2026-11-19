# Concat Web personal-admin release gates (manual VPS terminal, not yet deployed)

## Design and test prerequisites
1. Only one configured local Concat administrator. Require strong scrypt hashed password, root-owned private environment and independent 32+ byte session secret. No hard-coded credentials, no anonymous fallback, no public signup, no Scene DB or SSO dependency in explicit local mode.
2. Confirm protected UI/API reads and mutations enforce auth, CSRF, origin, revocable session, expiration, hashed credential verification and durable rate limiting. Foreign, ownerless and '__default__' rows remain quarantined, including admin and worker interactions.
3. Preserve the copied Cloud Render, Salad GPU, canonical Drive Bridge, verified MP4, OAuth/channel and persistent uploader queues. Verify owner-bound ingest/token and uploader bridge. Tests with fixtures are *not* a real Salad/YouTube acceptance run.
4. Run focused tests and build from the Concat repo: admin security (both legacy Scene fixture and new local-admin tests), foundation, reused modules, uploader contracts and guarded-helper syntax. CI must pass before merge. GitHub Actions is **not** a deployment mechanism.

## Safe manual release sequence (separately authorized)
1. Review PR, verify CI and merge verified code to protected 'concat-web/main'. Pin exact SHA, verify remote main identity and package that exact SHA.
2. Back up Concat private state and existing Concat helper/unit/Nginx routes before changing them. Preserve VPS_1/Scene production and other applications.
3. Root operator creates /etc/concat-web/concat-web.env mode 0600, with the local admin password hash and distinct random secrets generated only on VPS; never include secret values in GitHub, chat, terminal screenshots or shell trace.
4. The *currently installed* host /usr/local/sbin/concat-web-deploy may still require Scene SSO. Replace it only after verifying the new source/script digest and root-only permissions, preserving a rollback copy. Never invoke a stale helper for the new mode.
5. Run the new host-installed helper: 'preflight <verified-main-sha>'. Confirm it has no Scene DB/SSO requirements. Then secure-upload the checksum-verified package and run 'deploy <sha> <archive> <digest>' for Concat-only loopback service.
6. Confirm /healthz, 401 on anonymous endpoints, 200 on local-admin login and authenticated dashboard, CSRF enforcement, session revocation, Concat-only storage, and no regression on 'app.scenebuilder.online'.
7. With backup and rollback, configure separate HTTPS/Nginx routing for 'concat.scenebuilder.online'; Nginx -t, test public login and private endpoints. Restore only Concat release/route on failure. Never restart Scene, alter Drive Bridge/OAuth/Salad or deploy via GitHub Actions.
8. Real GPU → checksum-verified MP4 → uploader queue → controlled YouTube/OAuth acceptance remains a distinct live integration check before declaring the entire workflow production ready.

Historical Scene SSO audit and the failed VPS1 LUT staging release remain recorded in 'docs/VPS_TERMINAL_DEPLOY_AUDIT_20261119.md', but are not prerequisites for personal local-admin deployment.
