#!/usr/bin/env sh
# Uninstall ai-detector-cli (installs made by install.sh).
# Usage: sh uninstall.sh [--prefix DIR]
set -eu

PREFIX="${HOME}/.local"
[ "$1" = "--prefix" ] && PREFIX="$2" || true

INSTALL_DIR="${PREFIX}/share/ai-detector-cli"
BIN_DIR="${PREFIX}/bin"

rm -rf "${INSTALL_DIR}"
rm -f "${BIN_DIR}/ai-detect"
rm -f "${PREFIX}/share/bash-completion/completions/ai-detect"
rm -f "${PREFIX}/share/zsh/site-functions/_ai-detect"
rm -f "${PREFIX}/share/fish/vendor_completions.d/ai-detect.fish"

# Remove directories we created if they are now empty (best effort).
rmdir "${BIN_DIR}" 2>/dev/null || true
rmdir "${PREFIX}/share/bash-completion/completions" 2>/dev/null || true
rmdir "${PREFIX}/share/bash-completion" 2>/dev/null || true
rmdir "${PREFIX}/share/zsh/site-functions" 2>/dev/null || true
rmdir "${PREFIX}/share/zsh" 2>/dev/null || true
rmdir "${PREFIX}/share/fish/vendor_completions.d" 2>/dev/null || true
rmdir "${PREFIX}/share/fish" 2>/dev/null || true

echo "ai-detector-cli uninstalled (removed ${INSTALL_DIR} and ${BIN_DIR}/ai-detect)."
echo "If you pip-installed it too, run: pip uninstall ai-detector-cli"
