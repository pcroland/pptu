#!/bin/sh

if ! [ -x "$(command -v poetry)" ]; then
  echo "ERROR: poetry is not installed. Please install it and try again." >&2
  exit 1
fi

poetry config virtualenvs.in-project true
poetry install
if [ -f ".venv/bin/pptu" ]; then 
    mkdir -p ~/.local/bin
    ln -sf "$(realpath .venv/bin/pptu)" ~/.local/bin/
  else
    echo "ERROR: .venv/bin/pptu doesn't exist."
fi
