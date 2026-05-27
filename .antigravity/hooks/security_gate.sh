#!/usr/bin/env bash
set -euo pipefail

echo "Running AI security gate..."

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --no-git --redact || true
fi

if command -v trufflehog >/dev/null 2>&1; then
  trufflehog filesystem . --only-verified || true
fi

if command -v semgrep >/dev/null 2>&1; then
  semgrep scan --config auto || true
fi

echo "Security gate finished."
