"""Logs never keep serials, device IDs or the home folder; USB only"""

import os

from config.config_print import NETWORK_PRINTING
from utils.util_logging import redact_text


def test_redacts_ids():
    line = f"uuid 5c1e0f2a-7b3d-4e8f-9a01-deadbeef4242 MFG:Canon;SN:ABC123XYZ;MDL:TR150 in {os.path.expanduser('~')}/x"
    out = redact_text(line)
    assert "deadbeef4242" not in out and "ABC123XYZ" not in out
    assert os.path.expanduser("~") not in out


def test_network_printing_off():
    assert NETWORK_PRINTING is False
