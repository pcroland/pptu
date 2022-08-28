#!/bin/sh

if ! [ -x "$(command -v poetry)" ]; then
  echo "ERROR: poetry is not installed. Please install it and try again." >&2
  exit 1
fi

poetry config virtualenvs.in-project true
poetry install
mkdir -p ~/.local/bin
ln -sf "$(realpath .venv/bin/pptu)" ~/.local/bin/
