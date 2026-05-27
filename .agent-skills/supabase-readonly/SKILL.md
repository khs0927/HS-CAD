# Supabase Read-Only Skill

Use this skill for Supabase work.

Rules:
- Read schema before changing.
- Use read-only queries first.
- Never run migrations against production without approval.
- Do not print DB URLs or service role keys.
- Treat RLS policies as security-sensitive.
- Ask approval for INSERT/UPDATE/DELETE/ALTER/DROP/TRUNCATE.

Verification:
- schema inspected
- migration risk documented
- RLS impact documented
- rollback plan included
