# Concat Web: repository guide

Source review: 21 November 2026. This is a source map, not a claim about live deployment health.

FastAPI dashboard, Concat Studio, uploader and administration application. Scene SSO and per-owner data boundaries are part of the runtime contract.

## Source map

| Path | Purpose |
| --- | --- |
| [`app/`](../app/) | Application, templates and feature modules |
| [`reused/`](../reused/) | Reused uploader implementation |
| [`pyproject.toml`](../pyproject.toml) | Python dependencies and wheel package metadata |
| [`tests/`](../tests/) | Foundation, integration and security checks |
| [`deploy/RELEASE_GATES.md`](../deploy/RELEASE_GATES.md) | Deployment prerequisites and release gates |

## Development and validation

Create a virtual environment, install with python -m pip install -e '.[test]', and run the commands in README.md and .github/workflows/foundation-ci.yml. python run.py uses the loopback listener; protected routes require the configured Scene SSO integration.

## Build and storage policy

The target retention policy is 3 days for PR/test packages, 7 days for ordinary development candidates and sanitized failure diagnostics, and versioned GitHub Releases for supported downloads. The workflow's explicit retention-days is authoritative; this document alone does not change expiry. Release evidence consumed by another workflow needs its own retention exception.

Before retiring any artifact, identify its full source SHA and active consumers. Preserve active integration candidates and the current and previous verified release outside short-lived Actions storage. A candidate that needs longer testing must be copied to a named prerelease with checksums before expiry. No automatic artifact, branch, release or package deletion is introduced by this guide.

Heavy Windows/container packaging should use explicit release or manual triggers where source tests can run independently. Existing frozen-binary, media and compatibility tests remain release gates. Do not cancel an in-progress publication or deployment just to save CI minutes.

## Release record

For each release record: component/version, full source SHA, package SHA256 or container digest, relevant dependency/model versions, exact verification results, unresolved platform acceptance, and previous verified version/rollback procedure. Use sanitized screenshots from the actual app when available; no fabricated UI or unverified production claims.

## Maintenance checklist

- Keep README setup instructions and app/version mappings aligned with the source.
- Review dependency updates with the affected tests; do not enable blind automatic merges.
- Keep workflow token permissions scoped to the job that needs them.
- Inspect repository rules, environment protection and available security features before proposing account-setting changes.
- Keep historical research labelled and separate from the current source contract.
- Use the [contribution guide](../CONTRIBUTING.md) and issue/PR templates for review.
