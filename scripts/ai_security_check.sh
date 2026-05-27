#!/usr/bin/env bash
set -euo pipefail

echo "AI security check started"

command -v gitleaks >/dev/null 2>&1 && gitleaks detect --source . --no-git --redact || true
command -v trufflehog >/dev/null 2>&1 && trufflehog filesystem . --only-verified || true
command -v semgrep >/dev/null 2>&1 && semgrep scan --config auto || true

echo "AI security check finished"
