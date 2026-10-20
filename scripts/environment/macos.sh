#!/usr/bin/env bash
# macOS implementation; invoked by ../setup.sh. Requires Bash 3.2 or newer.
set -eu

mode=${1:-install}
case "$mode" in install|--check|--dry-run) ;; *) exit 2 ;; esac
[ "$#" -le 1 ] || exit 2
script_dir=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
root=$(CDPATH='' cd -- "$script_dir/../.." && pwd -P)
venv="$root/.venv"
export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_UPGRADE=1 HOMEBREW_NO_ANALYTICS=1
export PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INPUT=1 PIP_NO_CACHE_DIR=1

fail() { printf '%s\n' "$2" >&2; exit "$1"; }
recovery() {
    fail 3 'Existing .venv is incompatible or incomplete. Preserve it: move .venv to a backup location, then rerun make environment. Nothing was replaced.'
}

# macOS sort lacks -V. Compare the numeric major/minor from tool version output.
check_version() {
    tool_version=$("$1" --version) || fail 1 "Cannot run $1; repair its Homebrew formula."
    printf '%s\n' "$tool_version"
    if ! printf '%s\n' "$tool_version" | awk -v major="$2" -v minor="$3" '
        { for (i=1; i<=NF; i++) if ($i ~ /^[0-9]+\.[0-9]+/) {
            split($i, v, "."); found=1;
            ok=(v[1]>major || (v[1]==major && v[2]>=minor)); exit
        }} END { exit !(found && ok) }'; then
        fail 1 "Unsupported version from $1. Requires >= $2.$3; update that formula manually and rerun make environment."
    fi
}

architecture=$(uname -m)
printf 'macOS %s; CPU: %s\n' "$(sw_vers -productVersion)" "$architecture"
case "$architecture" in arm64|x86_64) ;; *) fail 1 "Unsupported CPU: $architecture" ;; esac
if [ "$(sysctl -in sysctl.proc_translated 2>/dev/null || true)" = 1 ]; then
    fail 1 'Rosetta shell detected. Open a native Apple Silicon terminal and rerun make environment.'
fi
if ! developer_dir=$(xcode-select -p 2>/dev/null); then
    fail 1 'Xcode Command Line Tools are missing. Run xcode-select --install manually, complete installation, then rerun make environment. Official guide: https://developer.apple.com/xcode/resources/'
fi
# Avoid xcrun and /usr/bin developer shims: a lookup can populate external caches.
make_command="$developer_dir/usr/bin/make"
compiler="$developer_dir/usr/bin/clang++"
if [ ! -x "$compiler" ]; then
    compiler="$developer_dir/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang++"
fi
[ -x "$make_command" ] && [ -x "$compiler" ] || fail 1 'GNU Make or Clang C++ is missing. Repair Xcode Command Line Tools, then rerun make environment.'
# Direct Clang does not select the SDK automatically as the developer shim does.
# Resolve it under the same selected developer directory without cache-writing tools.
SDKROOT="$developer_dir/SDKs/MacOSX.sdk"
if [ ! -d "$SDKROOT" ]; then
    SDKROOT="$developer_dir/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"
fi
[ -d "$SDKROOT" ] || fail 1 'macOS SDK is missing from the selected developer directory. Repair Xcode Command Line Tools or select a complete Xcode installation, then rerun make environment.'
export SDKROOT
printf 'macOS SDK: %s\n' "$SDKROOT"

brew_command=$(command -v brew || true)
if [ -z "$brew_command" ]; then
    case "$architecture" in arm64) candidate=/opt/homebrew/bin/brew ;; x86_64) candidate=/usr/local/bin/brew ;; esac
    if [ -x "$candidate" ]; then brew_command=$candidate; fi
fi
[ -n "$brew_command" ] || fail 1 'Homebrew is missing. Follow https://brew.sh manually, then rerun make environment. Setup never installs Homebrew or invokes sudo.'
if ! prefix=$("$brew_command" --prefix) || [ ! -d "$prefix" ]; then
    fail 1 'Homebrew could not report a valid prefix. Repair your installation using https://brew.sh, then rerun make environment.'
fi
case "$architecture:$prefix" in
    arm64:/usr/local|x86_64:/opt/homebrew) fail 1 'Homebrew prefix does not match the native CPU. Use native Homebrew and rerun make environment.' ;;
esac
printf 'Homebrew prefix: %s\n' "$prefix"
"$brew_command" --version || fail 1 'Homebrew cannot run. Repair it using https://brew.sh.'

# This intentionally accepts only the minimal Brewfile declaration format used here.
# It avoids brew bundle/list/info in read-only modes: those may fetch API metadata.
formulae=()
declaration='^[[:space:]]*brew[[:space:]]+"([A-Za-z0-9@+._-]+)"[[:space:]]*$'
while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|\#*) continue ;; esac
    if [[ $line =~ $declaration ]]; then
        formulae+=("${BASH_REMATCH[1]}")
    else
        fail 4 'Unsupported Brewfile declaration. Use one brew "formula" entry per line.'
    fi
done < "$root/Brewfile"
[ "${#formulae[@]}" -gt 0 ] || fail 4 'Brewfile has no required formulae.'

formula_executable() {
    case "$1" in
        python@3.14) printf '%s/opt/%s/bin/python3.14\n' "$prefix" "$1" ;;
        git|gh|z80dasm|mame|openmsx|shellcheck) printf '%s/opt/%s/bin/%s\n' "$prefix" "$1" "$1" ;;
        *) fail 4 "Unknown bootstrap formula: $1" ;;
    esac
}
missing=()
for formula in "${formulae[@]}"; do
    executable=$(formula_executable "$formula")
    if [ ! -x "$executable" ]; then
        missing+=("$formula")
        printf 'MISSING: Homebrew formula %s\n' "$formula"
    fi
done
if [ -x "$prefix/opt/git/bin/git" ]; then check_version "$prefix/opt/git/bin/git" 2 30; fi
if [ -x "$prefix/opt/gh/bin/gh" ]; then check_version "$prefix/opt/gh/bin/gh" 2 0; fi
python="$prefix/opt/python@3.14/bin/python3.14"
verify() {
    "$1" -I -B "$script_dir/verify_python.py" "$2" --root "$root" --base "$python" --architecture "$architecture"
}
toolchain() {
    "$python" -I -B "$script_dir/toolchain.py" --mode "$1" --root "$root" --prefix "$prefix" --make "$make_command" --cxx "$compiler"
}

has_venv=false
if [ -e "$venv" ] || [ -L "$venv" ]; then
    has_venv=true
    [ ! -L "$venv" ] && [ -f "$venv/pyvenv.cfg" ] && [ -x "$venv/bin/python" ] || recovery
    [ -x "$python" ] || fail 3 'Cannot validate existing .venv because Homebrew python@3.14 is missing. Restore that base Python manually, or preserve and move .venv to a backup location, then rerun make environment. Nothing was replaced.'
fi
if [ -x "$python" ]; then
    verify "$python" base || fail 1 'Homebrew Python is incompatible. Repair python@3.14, then rerun make environment.'
    if $has_venv; then verify "$venv/bin/python" environment || recovery; fi
fi

if [ "$mode" = --dry-run ]; then
    if [ "${#missing[@]}" -gt 0 ]; then
        for formula in "${missing[@]}"; do printf 'Would run: brew install %s\n' "$formula"; done
    fi
    if [ -x "$python" ]; then
        toolchain dry-run
    else
        printf '%s\n' 'Would provision pinned local sjasmplus, run ShellCheck and verify a synthetic MSX ROM after Python is installed.'
    fi
    if ! $has_venv; then printf 'Would create: %s (Python 3.14 venv)\n' "$venv"; fi
    if ! $has_venv || [ ! -x "$python" ] || ! verify "$venv/bin/python" dependencies >/dev/null 2>&1; then
        printf 'Would install pinned requirements from: %s\n' "$root/requirements.txt"
    fi
    printf '%s\n' 'Would verify versions, dependency imports and pip check. No changes applied.'
    exit 0
fi

if [ "$mode" = --check ]; then
    unmet=0
    [ "${#missing[@]}" -eq 0 ] || unmet=1
    if ! $has_venv; then printf 'MISSING: %s; run make environment.\n' "$venv" >&2; unmet=1; fi
    if [ -x "$python" ]; then
        if toolchain check; then
            :
        else
            toolchain_status=$?
            [ "$toolchain_status" -ne 3 ] || exit 3
            unmet=1
        fi
    fi
    [ "$unmet" -eq 0 ] || exit 1
else
    if [ "${#missing[@]}" -gt 0 ]; then
        for formula in "${missing[@]}"; do
            "$brew_command" install "$formula" || fail 4 "brew install $formula failed. Resolve the reported Homebrew error and rerun make environment."
        done
    fi
fi

# Recheck after installing missing formulae as well.
check_version "$prefix/opt/git/bin/git" 2 30
check_version "$prefix/opt/gh/bin/gh" 2 0
verify "$python" base || fail 1 'Python 3.14 is unavailable or incompatible after package checks.'
if [ "$mode" != --check ]; then toolchain install; fi
if ! $has_venv; then
    "$python" -m venv "$venv" || fail 4 'Creating .venv failed. Preserve any partial environment, move it aside, resolve the Python error and rerun make environment.'
fi
verify "$venv/bin/python" environment || recovery
if ! verify "$venv/bin/python" dependencies; then
    if [ "$mode" = --check ]; then
        fail 1 'Pinned dependencies are missing or incompatible. Run make environment.'
    fi
    "$venv/bin/python" -I -B -m pip install --only-binary=:all: -r "$root/requirements.txt" || fail 4 'pip install failed. Check network access and wheel availability, then rerun make environment; the existing .venv is preserved.'
fi
verify "$venv/bin/python" dependencies || fail 4 'Dependency imports or versions failed verification. Run make environment after repairing the reported error.'
"$venv/bin/python" -I -B -m pip --version || fail 4 'pip cannot run; preserve and move the broken .venv aside, then rerun make environment.'
"$venv/bin/python" -I -B -m pip check || fail 4 'pip check failed. Resolve the reported dependency conflicts and rerun make environment.'
printf 'Environment ready. Project Python: %s/bin/python\n' "$venv"
printf '%s\n' 'GitHub authentication is separate: run gh auth login manually when needed.'
