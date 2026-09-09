set shell := ["bash", "-cu"]

default:
    just --list

setup:
    python3 -m venv .venv
    .venv/bin/python -m pip install -e ".[dev]"

install:
    ./script/install

test:
    .venv/bin/ruff format --check src tests
    .venv/bin/ruff check src tests
    .venv/bin/detect-secrets scan --baseline .secrets.baseline
    PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
