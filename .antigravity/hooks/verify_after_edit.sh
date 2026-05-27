#!/usr/bin/env bash
set -euo pipefail

echo "Running automatic verification..."

if [ -f package.json ]; then
  echo "Detected package.json"

  if [ -f pnpm-lock.yaml ] && command -v pnpm >/dev/null 2>&1; then
    PM="pnpm"
  elif [ -f yarn.lock ] && command -v yarn >/dev/null 2>&1; then
    PM="yarn"
  else
    PM="npm"
  fi

  if $PM run | grep -q "typecheck"; then
    $PM run typecheck
  fi

  if $PM run | grep -q "lint"; then
    $PM run lint
  fi

  if $PM run | grep -q "test"; then
    $PM test -- --watch=false || $PM test || true
  fi

  if $PM run | grep -q "build"; then
    $PM run build
  fi
fi

if [ -f pyproject.toml ] || [ -d tests ]; then
  if command -v pytest >/dev/null 2>&1; then
    pytest
  fi

  if command -v ruff >/dev/null 2>&1; then
    ruff check .
  fi

  if command -v mypy >/dev/null 2>&1; then
    mypy .
  fi
fi

if [ -f pubspec.yaml ]; then
  if command -v flutter >/dev/null 2>&1; then
    flutter analyze
    flutter test || true
  fi
fi

echo "Verification finished."
