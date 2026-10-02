"""The licence shipped with LinPrinter: CC BY-NC 4.0 in LICENSE.md (the 2026-10-01 rollout)."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHES = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-"})


def licence():
    """LICENSE.md with typographic dashes made plain, so the checks don't depend on typesetting"""
    with open(os.path.join(ROOT, "LICENSE.md"), encoding="utf-8") as f:
        return f.read().translate(DASHES)


def test_names_cc_by_nc_4_0():
    text = licence()
    assert "Creative Commons Attribution-NonCommercial 4.0 International" in text
    assert "CC BY-NC 4.0" in text
    assert "SPDX-License-Identifier: CC-BY-NC-4.0" in text


def test_links_the_official_legal_code():
    """The page is a plain-language summary; the official legal code governs and is linked"""
    text = licence()
    assert "https://creativecommons.org/licenses/by-nc/4.0/legalcode" in text
    assert "governs" in text


def test_keeps_the_copyright_line_and_the_noncommercial_terms():
    text = licence()
    assert "Copyright © 2026 MensuraMedia" in text
    assert "Commercial use is respectfully reserved" in text


def test_one_licence_file_and_the_old_bespoke_licence_is_gone():
    assert not os.path.exists(os.path.join(ROOT, "LICENSE"))
    assert "Community License" not in licence()
