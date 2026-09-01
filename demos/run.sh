#!/bin/sh
# Convenience runner: load local secrets, then run a demo from the repo root.
#   ./demos/run.sh dice
here="$(cd "$(dirname "$0")/.." && pwd)"
. "$here/.env"
exec /usr/local/bin/python3.13 "$here/demos/${1:-dice}.py"
