# Database Read-Only Policy

Default database mode is read-only.

Allowed by default:
- SELECT
- EXPLAIN
- DESCRIBE
- SHOW
- PRAGMA read-only inspection

Forbidden without explicit approval:
- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- TRUNCATE
- CREATE INDEX on production
- migration apply
- seed production
- destructive schema changes

For Firebase/Supabase/Postgres tasks:
1. Inspect config and schema first.
2. Use read-only MCP access first.
3. Document the proposed write operation before executing.
4. Ask for explicit approval before mutations.
5. Never touch production unless the user explicitly asks.
