"""CUPS output parsers and USB-only filtering"""

from backends.backend_cups import (
    is_local_uri,
    lp_options,
    parse_destinations,
    parse_device_uris,
    parse_jobs,
    queue_model,
    resolve_implicit,
    sort_queues,
)


def test_local_uris():
    assert is_local_uri("usb://Canon/TR150?serial=X")
    assert is_local_uri("ipp://Canon%20TR150%20series%20(USB)._ipp._tcp.local/")
    assert is_local_uri("ipp://127.0.0.1:60000/ipp/print")
    assert not is_local_uri("ipp://192.168.1.20/ipp/print")
    assert not is_local_uri("ipp://Office%20Printer._ipp._tcp.local/")


def test_parsers():
    dest = "Canon_TR150_series_USB temporary accepting implicitclass://Canon_TR150_series_USB/ ipp://Canon%20TR150%20series%20(USB)._ipp._tcp.local/"
    assert parse_destinations(dest) == [
        ("Canon_TR150_series_USB", "ipp://Canon%20TR150%20series%20(USB)._ipp._tcp.local/")
    ]
    assert parse_device_uris(
        "device for Canon_TR150_series_USB: implicitclass://Canon_TR150_series_USB/\n"
    ) == [("Canon_TR150_series_USB", "implicitclass://Canon_TR150_series_USB/")]
    assert queue_model("Canon_TR150_series_USB") == "Canon TR150 series"
    jobs = parse_jobs("Canon_TR150_series_USB-12 user 1024 Mon 22 Sep 2026 10:00:00\n")
    assert jobs[0]["number"] == 12 and jobs[0]["size"] == 1024


ANNOUNCED = ("Canon_TR150_series_USB", "ipp://Canon%20TR150%20series%20(USB)._ipp._tcp.local/")


def test_misdirected_queue_is_not_hidden_by_its_driverless_namesake():
    # 2026-10-01: a raw queue on a serial port carried the driverless queue's name
    usable, misdirected = sort_queues(
        [("Canon_TR150_series_USB", "serial:/dev/ttyS0?baud=115200")], [ANNOUNCED]
    )
    assert usable == []  # lp -d Canon_TR150_series_USB would reach the serial queue
    assert misdirected == [("Canon_TR150_series_USB", "serial:/dev/ttyS0?baud=115200")]


def test_cups_browsed_queue_resolves_to_its_printer():
    queue = ("Canon_TR150_series_USB", "implicitclass://Canon_TR150_series_USB/")
    announced = [
        ANNOUNCED,
        ("Canon_TR150_series_USB@localhost", "implicitclass://Canon_TR150_series_USB%40localhost/"),
    ]
    assert sort_queues([queue], announced) == ([queue], [])
    assert (
        resolve_implicit("implicitclass://Canon_TR150_series_USB%40localhost/", dict([ANNOUNCED]))
        == ANNOUNCED[1]
    )
    # a cups-browsed queue for a network printer stays out
    office = ("Office", "implicitclass://Office/")
    assert sort_queues([office], [("Office", "ipp://Office._ipp._tcp.local/")]) == ([], [])


def test_driverless_only_and_network_queues():
    assert sort_queues([], [ANNOUNCED]) == ([ANNOUNCED], [])
    assert sort_queues([("Lab", "ipp://192.168.1.20/ipp/print")], []) == ([], [])
    assert sort_queues([("Old", "usb://Canon/TR150")], []) == ([("Old", "usb://Canon/TR150")], [])


def test_lp_options():
    opts = lp_options(
        {"color": "monochrome", "quality": "draft", "size": "iso_a4_210x297mm", "type": "stationery"}
    )
    assert "print-color-mode=monochrome" in opts and "print-quality=3" in opts
    assert "media=iso_a4_210x297mm" in opts and "media-type=stationery" in opts
    assert "print-scaling=none" in opts
