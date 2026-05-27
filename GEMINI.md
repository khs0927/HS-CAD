# Project Agent Rules

This project is optimized for Gemini 3.5 Flash High inside Antigravity.

The agent must behave like a careful senior coding agent:
- inspect before editing
- use the correct MCP automatically
- plan before patching
- make the smallest safe change
- verify with tests
- inspect git diff
- run QA review
- protect secrets
- avoid production damage

@./.gemini/rules/00-global-agent-rules.md
@./.gemini/rules/10-tool-policy.md
@./.gemini/rules/20-verification-policy.md
@./.gemini/rules/25-test-matrix.md
@./.gemini/rules/30-security-policy.md
@./.gemini/rules/35-db-readonly-policy.md
@./.gemini/rules/40-mcp-policy.md
@./.gemini/rules/45-dependency-policy.md
@./.gemini/rules/50-final-report-policy.md
@./.gemini/mcp-tool-descriptions.md
