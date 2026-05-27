#!/usr/bin/env bash
set -euo pipefail

input="$(cat || true)"

query="$(echo "$input" | jq -r '.tool_input.query // .tool_input.sql // .tool_input.command // ""' 2>/dev/null || echo "")"

forbidden_regex='INSERT[[:space:]]+INTO|UPDATE[[:space:]]+|DELETE[[:space:]]+FROM|DROP[[:space:]]+|ALTER[[:space:]]+|TRUNCATE[[:space:]]+|CREATE[[:space:]]+TABLE|CREATE[[:space:]]+INDEX|GRANT[[:space:]]+|REVOKE[[:space:]]+'

if echo "$query" | grep -Ei "$forbidden_regex" >/dev/null 2>&1; then
  cat <<'JSON'
{
  "decision": "deny",
  "reason": "Database write or schema mutation detected. Use read-only queries unless the user explicitly approves this operation."
}
JSON
  exit 0
fi

cat <<'JSON'
{
  "decision": "allow"
}
JSON
