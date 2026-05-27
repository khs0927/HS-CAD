# AI Agent Operating Manual

## Purpose

This project is configured to make Gemini 3.5 Flash High behave like a careful senior coding agent inside Antigravity.

The model itself is not magically upgraded.
Instead, output quality is improved by forcing:

- better context
- current documentation
- symbol-aware code search
- structural refactoring
- browser verification
- test loops
- diff review
- safety checks
- domain-specific skills
- role-based QA review

## Default MCP usage

Context7:
Use for current docs and version-sensitive APIs.

Serena:
Use for symbol-level codebase understanding.

ast-grep:
Use for syntax-aware search and large refactors.

Playwright:
Use for UI/browser verification.

Git/GitHub:
Use for diff review and repository awareness.

Firebase/Supabase/Postgres:
Use read-only first. Never mutate production without approval.

## Recommended task flow

1. Architect Agent:
   - reads project
   - plans
   - does not edit

2. Builder Agent:
   - implements minimal change
   - runs tests

3. QA Reviewer Agent:
   - reviews git diff
   - finds risks
   - does not edit unless instructed

4. Security Reviewer Agent:
   - reviews secrets, auth, payment, DB, deploy risk

## Antigravity MCP setup

Open:

Agent panel
→ MCP Servers
→ Manage MCP Servers
→ View raw config

Merge the contents of:

.antigravity/mcp_config.template.json

Then restart MCP servers.

## Recommended install checks

Node / npm:
node -v
npm -v

uv / uvx:
uv --version
uvx --version

Serena:
serena --help

Playwright:
npx playwright install

Firebase:
npx firebase-tools@latest --version

Security tools:
gitleaks version
trufflehog --version
semgrep --version

## Safety

Never expose secrets.
Never run destructive commands without explicit approval.
Never modify protected paths without explicit approval.
Never mutate production DB without explicit approval.

## Short future prompt

For future tasks, the user can simply say:

"프로젝트 agent rules를 기본값으로 적용해줘. 관련 파일을 먼저 읽고, 필요한 MCP를 자동으로 사용하고, 최소 수정으로 구현한 뒤 테스트/타입체크/린트/빌드 가능한 검증을 실행하고 git diff까지 확인해서 보고해줘."
