#!/usr/bin/env sh
# Odysseus installer.
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/rahulgo445/AgenticHarness/main/install.sh)"
#
# Creates an isolated venv under ~/.odysseus, installs the package into it, and
# drops an `odysseus` shim in ~/.local/bin. Nothing global is touched. Override
# with env vars: ODYSSEUS_REPO, ODYSSEUS_REF, ODYSSEUS_VENV, ODYSSEUS_BIN.
set -eu

REPO="${ODYSSEUS_REPO:-https://github.com/rahulgo445/AgenticHarness}"
REF="${ODYSSEUS_REF:-main}"
VENV="${ODYSSEUS_VENV:-$HOME/.odysseus/venv}"
BIN="${ODYSSEUS_BIN:-$HOME/.local/bin}"
# Default to a GitHub source tarball (no git needed); override to pin a tag or
# point at a local checkout.
TARBALL="${ODYSSEUS_TARBALL:-$REPO/archive/refs/heads/$REF.tar.gz}"

say()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Find a Python >= 3.10.
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  command -v "$c" >/dev/null 2>&1 || continue
  v="$("$c" -c 'import sys; print("%d %d" % sys.version_info[:2])' 2>/dev/null)" || continue
  # shellcheck disable=SC2086
  set -- $v
  [ "$1" -eq 3 ] && [ "$2" -ge 10 ] && { PY="$c"; break; }
done
[ -n "$PY" ] || die "Python 3.10+ not found. Install it from python.org or your package manager."
say "Python: $("$PY" --version 2>&1) ($(command -v "$PY"))"

# 2. Isolated virtual environment.
say "Creating venv at $VENV"
rm -rf "$VENV"
"$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip

# 3. Install the package (tarball URL, so git is not required).
say "Installing odysseus-harness from $REF"
"$VENV/bin/python" -m pip install --quiet "$TARBALL"

# 4. Shim on PATH.
mkdir -p "$BIN"
cat > "$BIN/odysseus" <<EOF
#!/usr/bin/env sh
exec "$VENV/bin/odysseus" "\$@"
EOF
chmod +x "$BIN/odysseus"
say "Installed: $BIN/odysseus"

# 5. Nudges.
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) say "Add $BIN to PATH:  echo 'export PATH=\"$BIN:\$PATH\"' >> ~/.zshrc && exec \$SHELL" ;;
esac
[ -n "${ODYSSEUS_API_KEY:-}" ] || \
  say "Set your key:  echo 'export ODYSSEUS_API_KEY=<gemini key>' >> ~/.zshrc"

say "Done. Try:  odysseus -p \"build a snake game in one index.html\" -d ./snake"
