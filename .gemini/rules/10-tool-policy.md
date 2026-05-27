# Tool Policy

Use tools automatically.
Do not wait for the user to explicitly ask.

## Context7

Use Context7 before writing code involving:
- React
- Next.js
- Vue
- Svelte
- Flutter
- Firebase
- Supabase
- Prisma
- Drizzle
- Tailwind
- shadcn/ui
- Vite
- Node.js libraries
- Python libraries
- unfamiliar SDKs
- version-sensitive APIs
- authentication
- deployment configuration
- cloud provider SDKs
- payment APIs
- database clients

Before implementing with a library or SDK:
1. Search current docs using Context7.
2. Confirm the current API shape.
3. Then write code.

## Serena

Use Serena automatically for:
- large codebase exploration
- finding symbol definitions
- finding references
- understanding class/function relationships
- multi-file refactoring
- architecture analysis
- renaming symbols
- extracting functions/classes
- tracing call graphs

Do not perform cross-file symbol changes by blind search/replace.

## ast-grep

Use ast-grep automatically for:
- repository-wide code pattern search
- structural code modifications
- replacing imports
- finding function calls
- finding React component patterns
- TypeScript/JavaScript/Python syntax-aware changes

Before applying repository-wide edits:
1. Write or test an ast-grep pattern.
2. Show the expected match scope.
3. Apply only the minimal safe transformation.

## Playwright

Use Playwright automatically for:
- UI changes
- login/signup flows
- forms
- navigation
- dashboard changes
- modal/dialog behavior
- responsive layout
- visual behavior bugs
- browser interaction bugs

After UI changes:
1. Start the dev server if needed.
2. Run a smoke test.
3. Capture console errors.
4. Capture network errors.
5. Check mobile width around 390px.
6. Check desktop width around 1440px.
7. Fix and rerun if possible.

## Git / GitHub

Use Git tools automatically for:
- checking current branch
- checking changed files
- inspecting git diff
- reviewing patch size
- understanding recent changes

Before final response:
- Always inspect git diff.
- Never claim success without checking changes.

## Firebase / Supabase / Postgres

For backend/database tasks:
1. Inspect schema/config first.
2. Prefer read-only queries.
3. Never modify production data without explicit approval.
4. Never run destructive migration commands unless explicitly requested.
5. Never expose environment variables or secrets.
