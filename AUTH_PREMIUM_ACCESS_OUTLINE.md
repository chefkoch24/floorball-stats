# Auth + Premium Access Outline (Netlify + Pelican)

Date: 2026-03-16

## Goal

Enable login-gated and paid-gated content while keeping the site statically generated with Pelican.

## Key Principle

Static HTML generation is fine.  
Access control must happen at request/runtime:
- route protection (Netlify role rules),
- server-side token verification for premium data endpoints.

## Current Baseline in This Repo

- Static site via Pelican (`content/` -> `output/`).
- Deploy on Netlify.
- `netlify.toml` currently only sets Python version.

## Required Changes

## 1. Netlify Identity + Roles

What to configure:
- Enable Netlify Identity in site settings.
- Enable “Git Gateway” only if needed.
- Define roles (at minimum):
  - `member` (logged in),
  - `pro` (paid).

Why:
- Identity issues JWT (`nf_jwt`) used by Netlify and Functions.
- Roles drive protected route access.

## 2. Route Protection in `netlify.toml`

Add redirect/condition rules for protected paths.

Example:

```toml
[build.environment]
PYTHON_VERSION = "3.11.9"

[[redirects]]
  from = "/member/*"
  to = "/member/:splat"
  status = 200
  force = true
  conditions = { Role = ["member", "pro"] }

[[redirects]]
  from = "/premium/*"
  to = "/premium/:splat"
  status = 200
  force = true
  conditions = { Role = ["pro"] }

[[redirects]]
  from = "/member/*"
  to = "/login"
  status = 401
  force = true

[[redirects]]
  from = "/premium/*"
  to = "/login"
  status = 401
  force = true
```

Notes:
- Keep protected pages in separate paths (`/member/`, `/premium/`).
- Do not place sensitive payloads in public pages.

## 3. Content Segmentation in Pelican

Keep static build, but separate path spaces:
- public content stays under existing paths,
- member/premium pages generated under dedicated folders.

Options:
- Add specific `content/pages/member/*` and `content/pages/premium/*`.
- Or generate league premium reports into `content/premium/...`.

Needed updates:
- `pelicanconf.py`: include new content paths.
- Theme navigation (`themes/my-theme/templates/base.html`): show/hide links based on frontend auth state.

## 4. Protected Data via Netlify Functions

Create server-side endpoints for premium datasets:
- `netlify/functions/premium-data.js` (or `.ts`).

Function responsibilities:
1. Read JWT from `Authorization: Bearer ...` or Netlify identity context.
2. Verify token (using Netlify identity/JWKS workflow).
3. Check role/claims (`pro`).
4. Return data only if authorized; else `401/403`.

Why:
- Even with protected HTML, API responses must be server-authorized.
- Prevents direct scraping of premium JSON without entitlement.

## 5. Payment -> Entitlement Sync (Stripe)

Needed components:
- Stripe Checkout / Customer Portal.
- Webhook function:
  - `netlify/functions/stripe-webhook.js`.
- On successful subscription:
  - assign/update user role `pro` (via Identity Admin API or your user DB + custom claims).
- On cancellation/failure:
  - remove `pro`.

Important:
- Role assignment must be server-side and idempotent.
- Store mapping between Stripe customer and identity user.

## 6. Frontend Login State + UX

Add minimal auth client logic:
- login/signup/logout buttons,
- detect user + roles,
- guard premium link visibility in UI.

Files likely touched:
- `themes/my-theme/templates/base.html`
- optional small JS bundle in `themes/my-theme/static/js/auth.js`

UX detail:
- Hiding links is convenience only.
- Real security remains in route/function checks.

## 7. Data Pipeline Boundaries

No fundamental change needed in scrape/stats pipeline, but:
- keep premium-only outputs in non-public storage or protected endpoints.
- avoid embedding premium raw data into public markdown/frontmatter.

If premium artifacts are generated during build:
- do not output them into publicly accessible routes unless protected by Netlify role conditions.

## 8. Suggested Implementation Phases

Phase 1 (MVP, no billing):
1. Enable Identity.
2. Add `/member/*` protection in `netlify.toml`.
3. Add one protected page + one protected function.

Phase 2 (Paid access):
1. Add Stripe checkout.
2. Add webhook-based role assignment (`pro`).
3. Protect `/premium/*` and premium functions by `pro`.

Phase 3 (Hardening):
1. Audit that no premium data is shipped in public HTML/JSON.
2. Add tests for role-protected functions.
3. Add monitoring/logging for auth failures and webhook events.

## 9. What Is Not Secure (Do Not Rely On)

- Only hiding premium sections in frontend JS/CSS.
- Embedding premium data into public pages and “masking” it.
- Client-side-only JWT parsing without server-side authorization.

## 10. Minimal File Checklist for This Repo

- `netlify.toml`: add role-based redirects.
- `pelicanconf.py`: optionally include member/premium content directories.
- `themes/my-theme/templates/base.html`: auth-aware nav links.
- `netlify/functions/premium-data.js`: protected API endpoint.
- `netlify/functions/stripe-webhook.js`: payment entitlement sync.
- `docs/` or root notes for env vars:
  - `STRIPE_SECRET_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  - Netlify Identity admin credentials (if required by chosen role assignment path).

