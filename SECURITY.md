# Security Policy

## Supported Versions
This is an MVP (version 0.x). Only the `main` branch receives fixes.

## Reporting a Vulnerability
If you discover a security issue (e.g. secret exposure risk, injection vector, privilege escalation):
1. Do NOT create a public exploit proof-of-concept with active subscription identifiers.
2. Open a **GitHub Security Advisory** (preferred) or a private issue if available.
3. Provide reproduction steps, impact description, and suggested remediation if known.

Avoid filing issues for:
- Missing optional hardening (rate limiting, auth scopes) in a local‑only tool
- Dependency upgrade requests without an associated vulnerability (use a PR instead)

## Design Overview (Security / Privacy)
- Runs locally; backend exposes only read‑only Azure management & metadata queries.
- No resource creation / mutation endpoints.
- Authentication via `DefaultAzureCredential`; secrets are not stored or logged.
- Azure OpenAI key (if used) is only read from process environment.
- Plan data stays in browser memory; not persisted or transmitted anywhere except to the local backend for validation.

## Hardening Recommendations (Optional)
If you fork/adapt for multi‑user or hosted scenarios:
- Add authentication & authorization (e.g. Azure AD App registration + token validation middleware).
- Enforce `CORS_ALLOW_ORIGINS` to specific origins instead of `*`.
- Add request rate limiting / caching eviction guards.
- Introduce structured audit logging (excluding secrets) and log rotation.
- Containerize and run with a restricted network egress policy if desired.

## Dependency Management
Run `pip list --outdated` and `npm audit` periodically. Submit PRs for critical CVEs. Avoid adding heavy transitive dependencies unless required.

---
Thank you for helping keep the project safe for the community.
