# Security Policy

## Secret handling

Never print or expose:
- API keys
- tokens
- OAuth secrets
- private keys
- service account JSON
- .env values
- database URLs
- production credentials

If secrets are needed:
- refer to them by environment variable name only
- use placeholders
- document where the user should add them

## Protected paths

Do not modify these paths without explicit user approval:

- prod/
- live/
- infra/
- infrastructure/
- migrations/
- database/migrations/
- payment/
- payments/
- billing/
- auth/
- authentication/
- security/
- secrets/
- .env
- .env.local
- .env.production
- firebase.json
- firestore.rules
- storage.rules
- supabase/config.toml
- wrangler.toml
- vercel.json
- Dockerfile.prod
- docker-compose.prod.yml

If a task requires modifying one of these files:
1. Stop.
2. Explain why the file must be changed.
3. Ask for explicit approval.

## Forbidden commands unless explicitly approved

Never run these unless the current user message explicitly asks for them:

- git reset --hard
- git clean -fd
- git push --force
- rm -rf
- del /s /q
- drop database
- truncate table
- firebase deploy
- supabase db push to production
- production migration commands
- deleting cloud resources
- rotating or printing secrets

## Security scans

When possible, use:
- gitleaks
- trufflehog
- semgrep
- npm audit
- pip-audit

Never install or run unknown scripts without reviewing them first.
