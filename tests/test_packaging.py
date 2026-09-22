"""The installer script, the package list and the installer package stay in step"""

import hashlib
import json
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


def version():
    return read("VERSION").strip()


def test_install_script_packages_match_app_json():
    apt = json.loads(read("app.json"))["offline"]["apt"]
    packages = re.search(r"^PACKAGES=\((.*)\)$", read("install.sh"), re.M).group(1).split()
    assert packages == apt


def test_package_is_committed_with_checksum():
    deb = f"linprinter_{version()}_all.deb"
    path = os.path.join(ROOT, "dist", deb)
    assert os.path.exists(path), "run: bash tools/build-deb.sh"
    sums = dict(reversed(line.split()) for line in read("dist", "SHA256SUMS").splitlines())
    assert sums[deb] == hashlib.sha256(open(path, "rb").read()).hexdigest()


@pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="dpkg-deb missing")
def test_package_contents():
    path = os.path.join(ROOT, "dist", f"linprinter_{version()}_all.deb")
    info = subprocess.run(
        ["dpkg-deb", "-f", path, "Package", "Version", "Depends"], capture_output=True, text=True
    ).stdout
    assert f"Version: {version()}" in info and "Package: linprinter" in info
    for pkg in json.loads(read("app.json"))["offline"]["apt"]:
        assert pkg in info
    files = subprocess.run(["dpkg-deb", "-c", path], capture_output=True, text=True).stdout
    for needed in (
        "./usr/bin/linprinter",
        "./opt/linprinter/src/main.py",
        "./usr/share/applications/linprinter.desktop",
        "./opt/linprinter/LICENSE",
    ):
        assert needed in files
    assert "__pycache__" not in files and "/tests/" not in files
