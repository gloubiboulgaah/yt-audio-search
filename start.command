#!/bin/bash
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv || exit 1
.venv/bin/python -m pip install -q -U -r requirements.txt
exec .venv/bin/python app.py
