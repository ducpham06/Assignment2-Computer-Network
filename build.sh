#!/usr/bin/env bash
# Rebuild every generated artefact from tools/sot.py
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/build_configs.py
python3 tools/validate.py
python3 tools/build_inventory.py
python3 tools/build_ipplan.py
python3 tools/build_diagrams.py
python3 tools/build_docs.py
python3 tools/build_report_assets.py
(cd automation && python3 -m pytest -q)
if command -v latexmk >/dev/null; then
  (cd report && latexmk -xelatex -interaction=nonstopmode main.tex >/dev/null && echo "report/main.pdf built")
fi
