param(
  [switch]$FullPytest
)
$ErrorActionPreference = "Stop"
python -m src.main --help
python -m src.main env-check --help
python -m src.main collect-debug --help
python -m src.main analyze-architecture --help
python -m src.main classify-objects --help
python -m src.main capture-screen --help
python tools/prepare_public_release.py --help
if ($FullPytest) {
  python -m pytest -q
} else {
  python -m pytest tests/test_environment_check.py tests/test_layer_semantics.py tests/test_tools_help.py -q
}
