#!/bin/sh
# One-command setup of saved-reels-digest on macOS and Linux (install.ps1 is the Windows one).
#
# Finds Python 3.9 to 3.14, checks the computer with doctor.py, creates the private Python
# environment the plugin uses (setup_env.py, about a minute and ~600 MB the first time) and
# says how to add the plugin to Claude Code. Running it again is safe and quick.
#
#   From a clone:        sh install.sh [--check-only]
#   Without cloning:     curl -fsSL https://raw.githubusercontent.com/ArmasCitoZ/saved-reels-digest/main/install.sh | sh
#
#   --check-only         only check the computer; install nothing
#   SRD_PYTHON=/path     use this Python instead of looking for one
#   SRD_HOME=/folder     keep the files there instead of ~/saved-reels-digest
#
# Plain POSIX sh (dash on Debian/Ubuntu, bash or zsh elsewhere); tests/test_install_sh.py runs it.
set -eu

MIN_MINOR=9
MAX_MINOR=14 # newest Python every dependency has builds for: MAX_PYTHON in doctor.py
REPO_TARBALL=https://github.com/ArmasCitoZ/saved-reels-digest/archive/refs/heads/main.tar.gz

step() { printf '\n==> %s\n' "$1"; }
warn() { printf '%s\n' "$1" >&2; }

check_only=0
for arg in "$@"; do
    case $arg in
        --check-only) check_only=1 ;;
        -h | --help) sed -n '2,15p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) warn "Unknown option: $arg (use --check-only or --help)"; exit 2 ;;
    esac
done

# "3 13" for a working Python, nothing otherwise
python_version() {
    "$1" -c 'import sys; print(sys.version_info[0], sys.version_info[1])' 2>/dev/null || true
}

# Prints the Python to use. Newest supported first: plain python3 may be one too new
# for the dependencies (or too old, like the 3.9 of older macOS command line tools).
find_python() {
    if [ -n "${SRD_PYTHON:-}" ]; then
        printf '%s\n' "$SRD_PYTHON"
        return
    fi
    too_new=""
    minor=$MAX_MINOR
    candidates=""
    while [ "$minor" -ge "$MIN_MINOR" ]; do
        candidates="$candidates python3.$minor"
        minor=$((minor - 1))
    done
    for cmd in $candidates python3 python; do
        command -v "$cmd" >/dev/null 2>&1 || continue
        set -- $(python_version "$cmd")
        [ "${1:-}" = 3 ] || continue
        if [ "$2" -gt "$MAX_MINOR" ]; then
            [ -n "$too_new" ] || too_new=$cmd
        elif [ "$2" -ge "$MIN_MINOR" ]; then
            printf '%s\n' "$cmd"
            return
        fi
    done
    # only a too-new Python: worth trying, setup_env.py explains what to do if pip fails
    [ -z "$too_new" ] || printf '%s\n' "$too_new"
}

scripts_folder() {
    # inside a clone, use its scripts; piped into sh there is no file, so download them
    here=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || here=""
    if [ -n "$here" ] && [ -f "$here/skills/digest/scripts/setup_env.py" ]; then
        printf '%s\n' "$here/skills/digest/scripts"
        return
    fi
    step 'Downloading the plugin scripts from GitHub' >&2
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$REPO_TARBALL" | tar -xzf - -C "$tmp"
    else
        wget -qO- "$REPO_TARBALL" | tar -xzf - -C "$tmp"
    fi
    printf '%s\n' "$tmp"/*/skills/digest/scripts
}

printf 'saved-reels-digest: setup for macOS and Linux\n'

step "Looking for Python 3.$MIN_MINOR or newer"
python=$(find_python)
if [ -z "$python" ]; then
    warn 'Python 3 is not installed (or not in the PATH).'
    warn 'macOS: brew install python@3.14, or https://www.python.org/downloads/'
    warn 'Debian/Ubuntu: sudo apt install python3 python3-venv'
    warn 'Then run this again.'
    exit 1
fi
set -- $(python_version "$python")
if [ "${1:-}" != 3 ] || [ "$2" -lt "$MIN_MINOR" ]; then
    warn "$python is not Python 3.$MIN_MINOR or newer. Install a newer one (python.org/downloads)."
    exit 1
fi
printf 'Using Python %s.%s (%s)\n' "$1" "$2" "$python"
if [ "$2" -gt "$MAX_MINOR" ]; then
    warn "Python $1.$2 may be too new for some dependencies. If the setup fails, install"
    warn "Python 3.$MAX_MINOR too and run this again."
fi

tmp=$(mktemp -d 2>/dev/null || mktemp -d -t saved-reels-digest)
trap 'rm -rf "$tmp"' EXIT
scripts=$(scripts_folder)

step 'Checking this computer (doctor.py)'
if ! "$python" "$scripts/doctor.py"; then
    warn 'Fix the FAIL lines above and run this again.'
    exit 1
fi
if [ "$check_only" = 1 ]; then
    printf '\nCheck only: nothing was installed.\n'
    exit 0
fi

step 'Creating the Python environment (setup_env.py, first time about a minute)'
if ! "$python" "$scripts/setup_env.py"; then
    warn 'Setup failed: read the error above. Running this again resumes it.'
    case $(uname -s) in
        Linux) warn 'On Debian/Ubuntu a missing venv module is fixed with: sudo apt install python3-venv' ;;
    esac
    exit 1
fi

step 'Last step: add the plugin to Claude Code'
if ! command -v claude >/dev/null 2>&1; then
    printf 'Claude Code is not installed yet: https://code.claude.com/docs/en/setup\n'
    printf 'Install it, then:\n'
fi
printf 'Type "claude" and, inside Claude Code, run:\n'
printf '  /plugin marketplace add ArmasCitoZ/saved-reels-digest\n'
printf '  /plugin install saved-reels@saved-reels-digest\n'
printf 'Restart Claude Code and type /saved-reels:digest\n'
