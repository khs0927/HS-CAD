#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install -e ".[dev]"

if [[ -f apps/mobile-cad-chatgpt/package-lock.json ]]; then
  npm --prefix apps/mobile-cad-chatgpt ci
elif [[ -f apps/mobile-cad-chatgpt/package.json ]]; then
  npm --prefix apps/mobile-cad-chatgpt install
fi

mkdir -p outputs test-results
python -m src.main doctor || true

cat <<'EOF'

HS-CAD cloud development environment is ready.

Common commands:
  source .venv/bin/activate
  python -m pytest -q --disable-warnings --maxfail=1
  python -m src.main doctor

Mobile CAD app, when present on the current branch:
  npm --prefix apps/mobile-cad-chatgpt run dev -- --host 0.0.0.0
  npm --prefix apps/mobile-cad-chatgpt test

Use the Codespaces Ports panel to open ports 5173 or 8787 on your phone.
Windows COM, ZWCAD, Rhino and GUI tests require the optional Windows cloud runner.
EOF
