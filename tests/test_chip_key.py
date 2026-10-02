"""The status vocabulary: Ready · Busy · Needs you · Can't reach"""

from modules.manager_status import chip_key, needs_you_words


def test_no_answer_is_cant_reach():
    assert chip_key("error", "unknown", []) == "error"
    assert chip_key("error", None, []) == "error"


def test_a_printer_that_answers_with_a_problem_needs_you():
    assert chip_key("error", "stopped", ["other-error"]) == "attention"
    assert chip_key("error", "stopped", ["media-empty-error"]) == "attention"
    assert chip_key("warn", "idle", ["marker-supply-low-warning"]) == "attention"


def test_ready_and_busy():
    assert chip_key("ok", "idle", []) == "ok"
    assert chip_key("ok", "processing", []) == "busy"


def test_needs_you_words():
    assert needs_you_words(["media-empty-error"]) == "Load paper first"
