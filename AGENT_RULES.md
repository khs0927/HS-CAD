# AI Agent Rules for Antigravity

This project is optimized for Gemini 3.5 Flash High.

Default behavior:
- Think carefully before editing.
- Inspect relevant files first.
- Use Context7 for current docs and APIs.
- Use Serena for symbol/codebase understanding.
- Use ast-grep for structural search and safe refactors.
- Use Playwright for UI/browser verification.
- Use Git diff review before final response.
- Run tests/typecheck/lint/build when relevant.
- Never expose secrets.
- Never modify protected files without approval.
- Never run destructive commands without explicit approval.

Protected paths:
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
- .env*
- firebase.json
- firestore.rules
- storage.rules
- supabase/config.toml
- wrangler.toml
- vercel.json
- Dockerfile.prod
- docker-compose.prod.yml

Forbidden without explicit user approval:
- destructive git commands
- production deploys
- destructive database operations
- secret printing
- force pushes
- deleting cloud resources

Final response must always include:
- summary
- changed files
- verification results
- remaining risks
- rollback plan
- confidence score
