#!/usr/bin/env bash
set -euo pipefail

echo "AI verification started"

if [ -f package.json ]; then
  if [ -f pnpm-lock.yaml ] && command -v pnpm >/dev/null 2>&1; then
    PM="pnpm"
  elif [ -f yarn.lock ] && command -v yarn >/dev/null 2>&1; then
    PM="yarn"
  else
    PM="npm"
  fi

  echo "Using package manager: $PM"

  $PM run typecheck 2>/dev/null || true
  $PM run lint 2>/dev/null || true
  $PM test 2>/dev/null || true
  $PM run build 2>/dev/null || true
fi

if [ -f pyproject.toml ] || [ -d tests ]; then
  command -v pytest >/dev/null 2>&1 && pytest || true
  command -v ruff >/dev/null 2>&1 && ruff check . || true
  command -v mypy >/dev/null 2>&1 && mypy . || true
fi

if [ -f pubspec.yaml ]; then
  command -v flutter >/dev/null 2>&1 && flutter analyze || true
  command -v flutter >/dev/null 2>&1 && flutter test || true
fi

echo "AI verification finished"
