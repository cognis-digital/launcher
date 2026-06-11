#!/usr/bin/env bash
# ============================================================================
#  setup.sh — one-line bootstrap for the Cognis guided SETUP WIZARD.
#
#  Run:
#      ./setup.sh
#  ...and type a number. The wizard explains everything at your level (1-5).
#
#  This is the friendly front door. It launches cognis_setup.py (stdlib-only,
#  no dependencies) pointed at a tool manifest:
#    * a local MANIFEST.json if one sits next to this script, otherwise
#    * the canonical cognis-arsenal MANIFEST.json fetched from GitHub (raw).
#  If neither is reachable, the wizard still runs — fleet setup, configure,
#  health-check and help all work without any manifest.
#
#  Any extra args are passed straight through to the wizard, e.g.:
#      ./setup.sh --dry-run
#      ./setup.sh --manifest /path/to/MANIFEST.json
# ============================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo .)"
WIZARD="$SCRIPT_DIR/cognis_setup.py"
RAW_MANIFEST="https://raw.githubusercontent.com/cognis-digital/cognis-arsenal/main/MANIFEST.json"

# --- locate a WORKING Python 3 interpreter ----------------------------------
# Probe common names AND known Windows install paths; verify each actually runs
# Python 3 (skips the Windows "App execution alias" stub that only prints a
# Store hint and exits non-zero).
PY=""
_py_works() { "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[0]>=3 else 1)' >/dev/null 2>&1; }
for c in python3 python py \
         /c/Python314/python.exe /c/Python313/python.exe /c/Python312/python.exe \
         /c/Python311/python.exe /c/Python310/python.exe; do
  if command -v "$c" >/dev/null 2>&1 && _py_works "$c"; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Cognis setup needs Python 3. Install it, then re-run ./setup.sh" >&2
  exit 1
fi

if [ ! -f "$WIZARD" ]; then
  echo "cognis_setup.py not found next to setup.sh ($WIZARD)" >&2
  exit 1
fi

# --- if the caller already passed --manifest, don't second-guess them -------
for a in "$@"; do
  case "$a" in
    --manifest|--manifest=*) exec "$PY" "$WIZARD" "$@" ;;
  esac
done

# --- find a manifest: local first, then fetch the arsenal one ---------------
MANIFEST=""
for cand in "$SCRIPT_DIR/MANIFEST.json" "$SCRIPT_DIR/../_meta/cognis-arsenal/MANIFEST.json"; do
  if [ -f "$cand" ]; then MANIFEST="$cand"; break; fi
done

TMP=""
if [ -z "$MANIFEST" ]; then
  TMP="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/cognis-manifest.$$.json")"
  fetched=""
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$RAW_MANIFEST" -o "$TMP" 2>/dev/null && fetched=1
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMP" "$RAW_MANIFEST" 2>/dev/null && fetched=1
  fi
  if [ -n "$fetched" ] && [ -s "$TMP" ]; then
    MANIFEST="$TMP"
  else
    echo "  (couldn't fetch the tool catalog — the wizard still runs:" >&2
    echo "   AI-fleet setup, configure, health-check and help all work.)" >&2
  fi
fi

cleanup() { [ -n "$TMP" ] && [ -f "$TMP" ] && rm -f "$TMP" 2>/dev/null || true; }
trap cleanup EXIT

if [ -n "$MANIFEST" ]; then
  "$PY" "$WIZARD" --manifest "$MANIFEST" "$@"
else
  "$PY" "$WIZARD" "$@"
fi
