#!/usr/bin/env sh
# =============================================================================
# ai-detector-cli installer
#
#   curl -fsSL https://raw.githubusercontent.com/dustindog101/ai-detector-cli/main/install.sh | sh
#
# Installs the `ai-detect` command into a self-contained venv under
# $PREFIX/share/ai-detector-cli and symlinks the launcher into $PREFIX/bin.
# Shell completions (bash/zsh/fish) are installed when their standard
# directories exist.
#
# Flags:
#   --prefix DIR     install root (default: ~/.local)
#   --ref REF        git ref to install (default: main)
#   --repo URL       git repository (default: https://github.com/dustindog101/ai-detector-cli)
#   --from-local DIR install from an existing local checkout instead of cloning
#   --no-completions skip shell completion installation
#   -h | --help      show this help
#
# Re-running the installer performs an in-place update.
# =============================================================================
set -eu

PREFIX="${HOME}/.local"
REPO_URL="https://github.com/dustindog101/ai-detector-cli"
GIT_REF="main"
INSTALL_COMPLETIONS=1
FROM_LOCAL=""

print_help() {
    sed -n '2,26p' "$0"
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) PREFIX="$2"; shift 2 ;;
        --repo) REPO_URL="$2"; shift 2 ;;
        --ref) GIT_REF="$2"; shift 2 ;;
        --from-local) FROM_LOCAL="$2"; shift 2 ;;
        --no-completions) INSTALL_COMPLETIONS=0; shift ;;
        -h|--help) print_help ;;
        *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
    esac
done

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m ✓\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m ✗\033[0m %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || { err "python3 is required but was not found in PATH."; exit 1; }

PYVER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PYOK="$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 8) else 0)')"
[ "$PYOK" = "1" ] || { err "Python >= 3.8 required (found $PYVER)."; exit 1; }
ok "Python $PYVER detected"

INSTALL_DIR="${PREFIX}/share/ai-detector-cli"
BIN_DIR="${PREFIX}/bin"

# ---------------------------------------------------------------------------
# Fetch source (local checkout, git clone, or tarball fallback)
# ---------------------------------------------------------------------------
if [ -n "${FROM_LOCAL}" ]; then
    [ -f "${FROM_LOCAL}/pyproject.toml" ] || { err "--from-local must point to a checkout containing pyproject.toml"; exit 1; }
    say "Installing from local checkout: ${FROM_LOCAL}"
    rm -rf "${INSTALL_DIR}"
    mkdir -p "$(dirname "${INSTALL_DIR}")"
    cp -R "${FROM_LOCAL}" "${INSTALL_DIR}"
    rm -rf "${INSTALL_DIR}/.git" "${INSTALL_DIR}/.venv" 2>/dev/null || true
elif [ -d "${INSTALL_DIR}/.git" ]; then
    say "Updating existing installation at ${INSTALL_DIR}"
    git -C "${INSTALL_DIR}" fetch --depth 1 origin "${GIT_REF}" || true
    git -C "${INSTALL_DIR}" reset --hard "origin/${GIT_REF}" 2>/dev/null \
        || git -C "${INSTALL_DIR}" reset --hard HEAD
else
    say "Downloading ai-detector-cli (${GIT_REF})"
    rm -rf "${INSTALL_DIR}"
    mkdir -p "${INSTALL_DIR}"
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 --branch "${GIT_REF}" "${REPO_URL}" "${INSTALL_DIR}" 2>/dev/null \
            || git clone --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
    else
        ok "git not found - using tarball download"
        TMP_TGZ="$(mktemp /tmp/ai-detector-cli.XXXXXX.tar.gz)"
        # shellcheck disable=SC2086
        curl -fsSL "${REPO_URL}/archive/${GIT_REF}.tar.gz" -o "${TMP_TGZ}" \
            || { err "Download failed. Install git or check your network."; exit 1; }
        tar -xzf "${TMP_TGZ}" -C "${INSTALL_DIR}" --strip-components=1
        rm -f "${TMP_TGZ}"
    fi
fi
ok "Source ready at ${INSTALL_DIR}"

# ---------------------------------------------------------------------------
# Build an isolated venv (keeps the user's site-packages untouched)
# ---------------------------------------------------------------------------
say "Creating isolated virtual environment"
if [ ! -x "${INSTALL_DIR}/.venv/bin/python" ]; then
    python3 -m venv "${INSTALL_DIR}/.venv"
fi
"${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
"${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet "${INSTALL_DIR}"
ok "Package installed into venv"

# ---------------------------------------------------------------------------
# Launcher symlink
# ---------------------------------------------------------------------------
mkdir -p "${BIN_DIR}"
ln -sf "${INSTALL_DIR}/.venv/bin/ai-detect" "${BIN_DIR}/ai-detect"
chmod +x "${INSTALL_DIR}/.venv/bin/ai-detect" 2>/dev/null || true
ok "Launcher linked at ${BIN_DIR}/ai-detect"

# ---------------------------------------------------------------------------
# Shell completions
# ---------------------------------------------------------------------------
install_completion() {
    src="$1"; dest="$2"
    mkdir -p "$(dirname "$dest")" 2>/dev/null && cp "$src" "$dest" 2>/dev/null
}

if [ "$INSTALL_COMPLETIONS" = "1" ]; then
    if [ -d "${INSTALL_DIR}/completions" ]; then
        install_completion "${INSTALL_DIR}/completions/ai-detect.bash" "${PREFIX}/share/bash-completion/completions/ai-detect" \
            && ok "bash completion installed"
        install_completion "${INSTALL_DIR}/completions/_ai-detect" "${PREFIX}/share/zsh/site-functions/_ai-detect" \
            && ok "zsh completion installed"
        install_completion "${INSTALL_DIR}/completions/ai-detect.fish" "${PREFIX}/share/fish/vendor_completions.d/ai-detect.fish" \
            && ok "fish completion installed"
    fi
fi

# ---------------------------------------------------------------------------
# PATH hint
# ---------------------------------------------------------------------------
case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *)
        printf '\n\033[1;33m NOTE:\033[0m %s is not in your PATH.\n' "${BIN_DIR}"
        printf '       Add this to your shell profile (~/.bashrc, ~/.zshrc, or ~/.profile):\n\n'
        printf '           export PATH="%s:$PATH"\n\n' "${BIN_DIR}"
        ;;
esac

printf '\n'
say "Installation complete!"
printf '  Run:        %s\n' "ai-detect --help"
printf '  Quick try:  %s\n' "ai-detect --local-only README.md"
printf '  Update:     %s\n' "re-run this installer"
printf '  Uninstall:  %s\n' "sh uninstall.sh (from the repo) or rm -rf ${INSTALL_DIR} ${BIN_DIR}/ai-detect"
printf '\n'
