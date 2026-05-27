#!/usr/bin/env bash
set -euo pipefail

input="$(cat || true)"

path="$(echo "$input" | jq -r '.tool_input.path // .tool_input.file_path // .tool_input.command // ""' 2>/dev/null || echo "")"

protected_regex='(^|/)(prod|live|infra|infrastructure|migrations|payment|payments|billing|auth|authentication|security|secrets)(/|$)|(^|/)\.env|firebase\.json|firestore\.rules|storage\.rules|supabase/config\.toml|wrangler\.toml|vercel\.json|Dockerfile\.prod|docker-compose\.prod\.yml'

destructive_regex='git reset --hard|git clean -fd|git push --force|rm -rf|drop database|truncate table|firebase deploy|supabase db push|DROP TABLE|TRUNCATE TABLE|DELETE FROM'

if echo "$path" | grep -E "$protected_regex" >/dev/null 2>&1; then
  cat <<'JSON'
{
  "decision": "deny",
  "reason": "Protected path or sensitive config detected. Ask the user for explicit approval before modifying it."
}
JSON
  exit 0
fi

if echo "$path" | grep -Ei "$destructive_regex" >/dev/null 2>&1; then
  cat <<'JSON'
{
  "decision": "deny",
  "reason": "Destructive command detected. Ask the user for explicit approval before running it."
}
JSON
  exit 0
fi

cat <<'JSON'
{
  "decision": "allow"
}
JSON
