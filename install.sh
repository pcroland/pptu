#!/bin/sh

if ! [ -x "$(command -v poetry)" ]; then
  echo "ERROR: poetry is not installed. Please install it and try again." >&2
  exit 1
fi

poetry install

if [ -z "$VIRTUAL_ENV" ]; then
  echo "ERROR: Unable to find virtualenv." >&2
fi

executable="$VIRTUAL_ENV/bin/pptu"
if ! [ -f "$executable" ]; then
  echo "ERROR: $executable doesn't exist." >&2
  exit 1
fi
mkdir -p ~/.local/bin
ln -sf "$executable" ~/.local/bin/
