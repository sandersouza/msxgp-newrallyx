#!/usr/bin/env bash
# Public platform dispatcher. Compatible with stock macOS Bash 3.2.
set -eu

usage() {
    printf '%s\n' 'Usage: bash scripts/setup.sh [--check | --dry-run | --help]'
}

if [ "$#" -gt 1 ]; then
    usage >&2
    exit 2
fi
case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    ''|--check|--dry-run) ;;
    *) usage >&2; exit 2 ;;
esac

kernel=$(uname -s 2>/dev/null || printf unknown)
case "$kernel" in
    Darwin) platform=macOS ;;
    Linux) platform=Linux ;;
    MINGW*|MSYS*|CYGWIN*) platform=Windows ;;
    *)
        if [ "${OS:-}" = Windows_NT ]; then
            platform=Windows
        else
            platform=Unknown
        fi
        ;;
esac
printf 'Detected OS: %s (%s)\n' "$platform" "$kernel"
if [ "$platform" != macOS ]; then
    printf 'Environment setup for %s is not supported yet; only macOS is implemented.\n' "$platform" >&2
    exit 1
fi

script_dir=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
exec bash "$script_dir/environment/macos.sh" "$@"
