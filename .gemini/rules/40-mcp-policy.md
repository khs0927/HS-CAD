# MCP Policy

MCP usage must be automatic and task-based.

## Tool router

Use this routing table:

- Documentation/API/SDK/version-sensitive code:
  Use Context7.

- Large codebase structure, symbol definitions, references:
  Use Serena.

- Repository-wide pattern search or code transformation:
  Use ast-grep.

- UI/browser behavior:
  Use Playwright.

- Git diff, PR, branch, issue:
  Use Git/GitHub tools.

- Firebase/Supabase/Postgres:
  Use read-only database/cloud MCP first.

- Security scan:
  Use semgrep, gitleaks, trufflehog, or local scripts if available.

## MCP minimalism

Do not call every MCP blindly.
Choose the smallest correct tool set.

## MCP safety

Never allow MCP tools to:
- expose secrets
- modify production data
- run destructive shell commands
- bypass approval
- write to protected paths

## MCP fallback

If MCP is unavailable:
1. State that it is unavailable.
2. Use local project files and available CLI commands.
3. Document what should be installed or configured.
