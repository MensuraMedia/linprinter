#!/usr/bin/env bash
# build-deb.sh - build the LinPrinter installer package: dist/linprinter_<version>_all.deb
#
# The package installs the app to /opt/linprinter, a `linprinter` command, the menu entry and
# the icon, and depends only on distribution packages (the same list as app.json), so
#     sudo apt install ./dist/linprinter_<version>_all.deb
# pulls in anything missing - from the network, or from a local/offline apt source such as
# the linux-peripherals pool. No maintainer scripts; nothing is downloaded at build time.
#
# Usage: bash tools/build-deb.sh            (needs dpkg-deb; run from anywhere)

set -euo pipefail
export LC_ALL=C

APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$APP_DIR/VERSION")"
DIST="$APP_DIR/dist"
PKG="linprinter_${VERSION}_all"
DEPENDS="$(python3 -c "import json;print(', '.join(json.load(open('$APP_DIR/app.json'))['offline']['apt']))")"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ROOT="$STAGE/$PKG"
mkdir -p "$ROOT/DEBIAN" "$ROOT/opt/linprinter" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/512x512/apps" "$ROOT/usr/share/doc/linprinter"

# the app itself (no caches, tests or development tools)
cp -r "$APP_DIR/src" "$APP_DIR/resources" "$ROOT/opt/linprinter/"
cp "$APP_DIR/VERSION" "$APP_DIR/LICENSE" "$APP_DIR/README.md" "$APP_DIR/run.sh" "$ROOT/opt/linprinter/"
find "$ROOT/opt/linprinter" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$ROOT/opt/linprinter" -name '*.py[co]' -delete

cat > "$ROOT/usr/bin/linprinter" <<'EOF'
#!/bin/sh
# LinPrinter launcher (package install)
exec python3 /opt/linprinter/src/main.py "$@"
EOF

cat > "$ROOT/usr/share/applications/linprinter.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=LinPrinter
GenericName=Document Printer
Comment=Print documents, check ink, test and set up your USB printer, or print to PDF
Exec=linprinter %F
Icon=linprinter
StartupWMClass=linprinter
Terminal=false
Categories=Office;Printing;
MimeType=application/pdf;image/png;image/jpeg;image/tiff;image/bmp;image/gif;text/plain;text/csv;text/markdown;
Keywords=print;printer;pdf;ink;cups;test page;
EOF

cp "$APP_DIR/resources/images/logo.png" "$ROOT/usr/share/icons/hicolor/512x512/apps/linprinter.png"
cp "$APP_DIR/LICENSE" "$ROOT/usr/share/doc/linprinter/copyright"
gzip -9n < "$APP_DIR/changelog.md" > "$ROOT/usr/share/doc/linprinter/changelog.gz"

# permissions: directories 755, files 644, executables 755
find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT" -type f -exec chmod 644 {} +
chmod 755 "$ROOT/usr/bin/linprinter" "$ROOT/opt/linprinter/run.sh"

SIZE="$(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)"
cat > "$ROOT/DEBIAN/control" <<EOF
Package: linprinter
Version: $VERSION
Section: graphics
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: $DEPENDS
Maintainer: MensuraMedia <mensuramedia@gmail.com>
Homepage: https://github.com/MensuraMedia/linprinter
Description: document printer for USB printers (driverless IPP, CUPS, Print to PDF)
 LinPrinter prints PDFs, images and text on USB printers with only the options
 the printer really has, shows an exact preview, follows jobs in a queue, shows
 ink levels, prints test pages, opens the printer's maintenance page and prints
 to PDF. USB only: no network discovery, no telemetry.
 .
 Licence: LinPrinter Community License (Noncommercial) 1.0.
EOF
( cd "$ROOT" && find . -path ./DEBIAN -prune -o -type f -printf '%P\0' | sort -z | xargs -0 md5sum ) > "$ROOT/DEBIAN/md5sums"
chmod 644 "$ROOT/DEBIAN/control" "$ROOT/DEBIAN/md5sums"

mkdir -p "$DIST"
rm -f "$DIST"/linprinter_*_all.deb
dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$DIST/$PKG.deb" >/dev/null
( cd "$DIST" && sha256sum "$PKG.deb" > SHA256SUMS )
echo "built dist/$PKG.deb ($(du -h "$DIST/$PKG.deb" | cut -f1))"
cat "$DIST/SHA256SUMS"
