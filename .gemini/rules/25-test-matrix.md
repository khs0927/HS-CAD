# Test Matrix

Use this matrix to choose verification commands.

## TypeScript / JavaScript

If package.json exists:
- npm run typecheck if available
- npm run lint if available
- npm test if available
- npm run build if available

If pnpm-lock.yaml exists, prefer pnpm.
If yarn.lock exists, prefer yarn.
If package-lock.json exists, prefer npm.

## React / Next.js / Vite UI

For UI changes:
- run typecheck
- run lint
- run build
- run Playwright smoke test if available
- check browser console errors
- check responsive layout

## Firebase Functions

For Firebase Functions:
- inspect functions/package.json
- run lint if available
- run build if available
- run tests if available
- avoid firebase deploy unless explicitly requested

## Supabase

For Supabase:
- inspect schema/migrations
- use read-only queries first
- avoid production db push unless explicitly requested
- document migration risk

## Flutter

If pubspec.yaml exists:
- flutter analyze
- flutter test if available
- inspect affected screens
- avoid broad UI rewrite

## Python

If pyproject.toml or tests/ exists:
- pytest if available
- ruff check if available
- mypy if available
- python -m compileall if useful

## CAD / ZWCAD automation

For CAD automation code:
- run unit tests if available
- test parsing on sample files only
- never overwrite DWG files directly
- create dry-run JSON reports first
- back up files before modification
- separate read/extract from write/modify
