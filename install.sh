#!/usr/bin/env bash
# linprinter installer for Debian-based systems (Debian, Ubuntu, Linux Mint).
#
#   - installs missing dependencies (GTK 3 Python bindings, Pillow, CUPS, ipp-usb,
#     Ghostscript) from the linux-peripherals offline pool first (when LinPrinter is
#     checked out inside linux-peripherals), the network otherwise (asks for sudo only then)
#   - default: runs LinPrinter from this folder and adds it to YOUR desktop menu
#     (~/.local/share/applications), with its icon
#   - --package: installs the installer package dist/linprinter_<version>_all.deb system-wide
#     instead (checksum-verified against dist/SHA256SUMS; /opt/linprinter, `linprinter` command,
#     menu entry for every user)
#   - verifies the app starts, CUPS is running and ipp-usb is present
# Safe to re-run: it only changes what is missing or wrong.
#
# Run as your NORMAL user (it asks for sudo only when something must be installed).
# Usage: bash install.sh [--package | --uninstall]

set -u
export LC_ALL=C

APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO_ROOT="$(cd "$APP_DIR/.." && pwd)"
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications/linprinter.desktop"
PACKAGES=(python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil cups cups-client cups-filters cups-ipp-utils ipp-usb ghostscript fontconfig fonts-dejavu-core librsvg2-common)

if [[ $EUID -eq 0 && "${LINPRINTER_ALLOW_ROOT:-}" != 1 ]]; then  # LINPRINTER_ALLOW_ROOT=1: container tests only
    echo "Run this as your normal user (without sudo) - the menu entry is per-user."; exit 1
fi

if [[ -t 1 ]]; then G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; B=$'\e[1m'; N=$'\e[0m'; else G= Y= R= B= N=; fi
SUMMARY=(); FAILED=0
step()  { echo; echo "${B}==> $*${N}"; }
ok()    { echo "    ${G}OK${N}    $*"; SUMMARY+=("${G}OK${N}    $*"); }
fixed() { echo "    ${Y}FIXED${N} $*"; SUMMARY+=("${Y}FIXED${N} $*"); }
fail()  { echo "    ${R}FAIL${N}  $*"; SUMMARY+=("${R}FAIL${N}  $*"); FAILED=1; }
info()  { echo "          $*"; }
report() {
    echo; echo "${B}================ linprinter install summary ================${N}"
    printf '  %s\n' "${SUMMARY[@]}"
    if [[ "${MODE:-}" == "--uninstall" ]]; then
        [[ $FAILED -eq 0 ]] && echo "  ${G}${B}Result: LinPrinter removed${N}" || echo "  ${R}${B}Result: not fully removed - see FAIL lines above${N}"
        exit $FAILED
    fi
    [[ $FAILED -eq 0 ]] && echo "  ${G}${B}Result: LinPrinter ready - find it in the menu or run ${RUN:-$APP_DIR/run.sh}${N}" \
                        || echo "  ${R}${B}Result: setup incomplete - see FAIL lines above${N}"
    exit $FAILED
}

MODE="${1:-user}"
case "$MODE" in
    user|--package|--uninstall) ;;
    *) echo "Usage: bash install.sh [--package | --uninstall]"; exit 2 ;;
esac
USER_ICON="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps/linprinter.png"
VERSION="$(tr -d '[:space:]' < "$APP_DIR/VERSION")"
DEB="$APP_DIR/dist/linprinter_${VERSION}_all.deb"
RUN="$APP_DIR/run.sh"

if [[ "$MODE" == "--uninstall" ]]; then
    step "Uninstalling"
    rm -f "$DESKTOP" "$USER_ICON" && ok "Removed your menu entry and icon (dependencies and settings left in place)"
    if dpkg-query -W -f='${Status}' linprinter 2>/dev/null | grep -q "install ok installed"; then
        sudo dpkg -r linprinter >/dev/null && ok "Removed the linprinter package" || fail "Could not remove the linprinter package"
    fi
    report
fi

step "Checking dependencies"
MISSING=()
for p in "${PACKAGES[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || MISSING+=("$p")
done
if [[ ${#MISSING[@]} -eq 0 ]]; then
    ok "Dependencies present: ${PACKAGES[*]}"
elif [[ -x "$REPO_ROOT/bin/offline-install" ]] && sudo "$REPO_ROOT/bin/offline-install" "${MISSING[@]}" >/dev/null 2>&1; then
    fixed "Installed from offline pool: ${MISSING[*]}"
elif sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${MISSING[@]}" >/dev/null; then
    fixed "Installed from network: ${MISSING[*]}"
else
    fail "Could not install: ${MISSING[*]}"; report
fi

if [[ "$MODE" == "--package" ]]; then
    step "Installer package"
    if [[ ! -f "$DEB" ]]; then
        fail "Package not found: $DEB (build it with: bash tools/build-deb.sh)"; report
    fi
    if ! ( cd "$APP_DIR/dist" && sha256sum --quiet -c SHA256SUMS ) >/dev/null 2>&1; then
        fail "Checksum mismatch for $(basename "$DEB") - not installing it"; report
    fi
    ok "Package checksum verified ($(basename "$DEB"))"
    if [[ "$(dpkg-query -W -f='${Status} ${Version}' linprinter 2>/dev/null)" == "install ok installed $VERSION" ]]; then
        ok "linprinter $VERSION package installed"
    elif sudo dpkg -i "$DEB" >/dev/null 2>&1; then
        fixed "Installed linprinter $VERSION package (/opt/linprinter, menu entry for all users)"
    else
        fail "dpkg could not install $(basename "$DEB")"; report
    fi
    if [[ -f "$DESKTOP" || -f "$USER_ICON" ]]; then
        rm -f "$DESKTOP" "$USER_ICON"
        fixed "Removed the per-user menu entry (the package provides one; avoids a duplicate)"
    fi
    RUN=/usr/bin/linprinter
else

step "App icon (panel, Alt+Tab, menu)"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"
mkdir -p "$ICON_DIR"
if cmp -s "$APP_DIR/resources/images/logo.png" "$ICON_DIR/linprinter.png"; then
    ok "Icon installed ($ICON_DIR/linprinter.png)"
else
    cp "$APP_DIR/resources/images/logo.png" "$ICON_DIR/linprinter.png"
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "${ICON_DIR%/512x512/apps}" 2>/dev/null
    fixed "Installed icon ($ICON_DIR/linprinter.png)"
fi

step "Desktop menu entry"
mkdir -p "$(dirname "$DESKTOP")"
ENTRY="[Desktop Entry]
Type=Application
Name=LinPrinter
GenericName=Document Printer
Comment=Print documents, check ink, test and set up your USB printer, or print to PDF
Exec=$APP_DIR/run.sh %F
Icon=linprinter
StartupWMClass=linprinter
Terminal=false
Categories=Office;Printing;
MimeType=application/pdf;image/png;image/jpeg;image/tiff;image/bmp;image/gif;text/plain;text/csv;text/markdown;
Keywords=print;printer;pdf;ink;cups;test page;"
if [[ -f "$DESKTOP" ]] && [[ "$(cat "$DESKTOP")" == "$ENTRY" ]]; then
    ok "Menu entry present ($DESKTOP)"
else
    printf '%s\n' "$ENTRY" > "$DESKTOP" && chmod 644 "$DESKTOP"
    command -v update-desktop-database >/dev/null && update-desktop-database -q "$(dirname "$DESKTOP")" 2>/dev/null
    fixed "Added menu entry ($DESKTOP)"
fi

fi  # per-user install

step "Verifying"
VER=$("$RUN" --version 2>/dev/null)
[[ "${VER,,}" == linprinter* ]] && ok "App starts: $VER" || fail "App did not start: run $RUN to see the error"
if python3 -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk; import PIL' 2>/dev/null; then
    ok "GTK 3 and Pillow importable"
else
    fail "GTK 3 or Pillow missing from Python"
fi
if lpstat -r 2>/dev/null | grep -q "is running"; then ok "CUPS is running"
elif sudo systemctl enable --now cups >/dev/null 2>&1 && lpstat -r 2>/dev/null | grep -q "is running"; then fixed "Started CUPS"
else fail "CUPS is not running (sudo systemctl start cups)"; fi
if command -v ipp-usb >/dev/null; then ok "ipp-usb present (USB printers print driverless; it starts when a printer is plugged in)"
else fail "ipp-usb missing"; fi
if timeout 30 "$RUN" --list-printers 2>/dev/null | grep -v "^Print to PDF" | grep -q .; then
    ok "Printer found: $(timeout 30 "$RUN" --list-printers 2>/dev/null | grep -v '^Print to PDF' | head -1)"
else info "No printer connected right now - LinPrinter will find it when plugged in and switched on"; ok "Print to PDF available"; fi

report
