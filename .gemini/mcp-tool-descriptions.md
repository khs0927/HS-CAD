# MCP Tool Descriptions

## Context7

Use this before writing code that depends on external libraries, frameworks, SDKs, or cloud APIs.
Do not use it for simple local logic.

Best for:
- current docs
- SDK usage
- version-specific API shape
- framework configuration
- auth/provider examples
- Firebase/Supabase/React/Next/Flutter docs

## Serena

Use this for symbol-level codebase understanding.

Best for:
- find definitions
- find references
- understand call graph
- multi-file refactor
- architecture analysis
- class/function relationship

Do not replace Serena with blind grep for cross-file symbol work.

## ast-grep

Use this for syntax-aware pattern search and repository-wide transformations.

Best for:
- import replacement
- function call pattern search
- component usage search
- structural refactor
- safe mass edits

Never use blind search/replace for code structure changes.

## Playwright

Use this after UI changes.

Best for:
- browser smoke test
- forms
- modals
- navigation
- login flow
- responsive check
- console/network error check
- screenshot capture

## Git/GitHub

Use this for:
- branch status
- changed files
- diff review
- issue/PR context
- patch size
- rollback planning

## Database MCP

Use read-only queries first.

Allowed by default:
- SELECT
- EXPLAIN
- DESCRIBE
- SHOW

Forbidden without approval:
- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- TRUNCATE
- production migrations
