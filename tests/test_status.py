"""Plain-language printer states"""

from modules.manager_status import POWER_OFF, describe, ink_warnings, user_must_act


def test_unreachable():
    assert describe("idle", [], reachable=False) == ("error", POWER_OFF)


def test_ready_and_printing():
    assert describe("idle", ["none"]) == ("ok", "Ready")
    assert describe("processing", []) == ("ok", "Printing…")


def test_paper_out_needs_user():
    level, message = describe("stopped", ["media-empty-error"])
    assert level == "error" and "paper" in message.lower()
    assert user_must_act(["media-empty-error"])
    assert not user_must_act(["marker-supply-low-warning"])


def test_unknown_reason_is_readable():
    level, message = describe("idle", ["strange-thing-warning"])
    assert level == "warn" and "strange thing" in message


def test_ink_warnings():
    markers = [{"name": "Color", "level": 10}, {"name": "Black", "level": 0}, {"name": "Photo", "level": 80}]
    assert ink_warnings(markers, 15) == ["Color ink is low (10 %).", "Black ink is empty."]
    assert ink_warnings([{"name": "X", "level": -1}], 15) == []
