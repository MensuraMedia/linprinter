"""The licence shipped with LinPrinter is CC BY-NC 4.0, summary and full legal code."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def licence():
    with open(os.path.join(ROOT, "LICENSE"), encoding="utf-8") as f:
        return f.read()


def test_names_cc_by_nc_4_0():
    text = licence()
    assert "Creative Commons Attribution-NonCommercial 4.0 International" in text
    assert "CC BY-NC 4.0" in text
    assert "https://creativecommons.org/licenses/by-nc/4.0/" in text


def test_carries_the_full_legal_code_not_only_the_summary():
    """The deed is not a substitute for the licence, so the legal code ships with it"""
    text = licence()
    for section in (
        "Section 1 -- Definitions.",
        "Section 2 -- Scope.",
        "Section 3 -- License Conditions.",
        "Section 5 -- Disclaimer of Warranties and Limitation of Liability.",
        "Section 8 -- Interpretation.",
    ):
        assert section in text, section
    assert "Creative Commons may be contacted at creativecommons.org." in text


def test_keeps_the_copyright_line_and_the_noncommercial_terms():
    text = licence()
    assert "Copyright (c) 2026 MensuraMedia" in text
    assert "Commercial use is not permitted without explicit permission" in text


def test_the_old_bespoke_licence_is_gone():
    assert "Community License" not in licence()
