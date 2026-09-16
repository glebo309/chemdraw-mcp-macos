#!/bin/sh
# Install the locked checkout environment and enter interactive terminal setup.
set -eu
INSTALL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$INSTALL_ROOT"
if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2
    printf '%s\n' 'Prefer no terminal? Download the Mac DMG from the GitHub Releases page.' >&2
    exit 1
fi
uv sync --locked --extra chemistry
exec uv run --locked --extra chemistry chemdraw-mac setup "$@"
