"""Page selection and rendering (Ghostscript)"""

import os

import pytest
from PIL import Image

from conftest import requires_gs
from modules import manager_render as render
from modules.manager_testpage import KINDS, make_test_page

TICKET = {
    "size": "iso_a4_210x297mm",
    "size_mm": (210, 297),
    "type": "stationery",
    "borderless": False,
    "margins_mm": (5, 3.4, 5, 3.4),
    "color": "color",
    "quality": "normal",
    "copies": 1,
    "scaling": "fit",
    "dpi": 600,
}


def test_select_pages():
    assert render.select_pages("all", 4) == [1, 2, 3, 4]
    assert render.select_pages("odd", 5) == [1, 3, 5]
    assert render.select_pages("even", 5) == [2, 4]
    assert render.select_pages("current", 5, current=9) == [5]
    assert render.select_pages("range", 10, "1-3, 5, 8-") == [1, 2, 3, 5, 8, 9, 10]
    with pytest.raises(render.RenderError):
        render.select_pages("range", 3, "abc")
    with pytest.raises(render.RenderError):
        render.select_pages("range", 3, "7")


@pytest.fixture
def sample(tmp_path):
    pages = [Image.new("RGB", (620, 877), c) for c in ("white", "red", "blue")]
    path = tmp_path / "sample.pdf"
    pages[0].save(path, save_all=True, append_images=pages[1:])
    return str(path)


@requires_gs
def test_normalise_and_count(tmp_path, sample):
    assert render.page_count(sample) == 3
    img = tmp_path / "photo.png"
    Image.new("RGB", (400, 300), "green").save(img)
    pdf = render.normalise(str(img), str(tmp_path / "work"))
    assert render.page_count(pdf) == 1
    txt = tmp_path / "notes.txt"
    txt.write_text("hello\n" * 200)
    assert render.page_count(render.normalise(str(txt), str(tmp_path / "work"))) >= 2


@requires_gs
def test_render_pwg(tmp_path, sample):
    out = render.render_pwg(sample, [1, 3], dict(TICKET, color="monochrome"), str(tmp_path / "job.pwg"))
    data = open(out, "rb").read()
    assert data.startswith(b"RaS2")
    assert data.count(b"PwgRaster") == 2  # one header per page


@requires_gs
def test_render_pdf_and_preview(tmp_path, sample):
    out = render.render_pdf(sample, [2], TICKET, str(tmp_path / "out.pdf"))
    assert render.page_count(out) == 1
    previews = render.render_preview(sample, [1, 2], TICKET, str(tmp_path / "prev"))
    assert len(previews) == 2 and all(os.path.exists(p) for p in previews)


@requires_gs
@pytest.mark.parametrize("kind", list(KINDS))
def test_test_pages(tmp_path, kind):
    out = make_test_page(
        kind, str(tmp_path / f"{kind}.pdf"), (215.9, 279.4), (5, 3.4, 5, 3.4), "Test", TICKET, "2.060"
    )
    assert render.page_count(out) == 1
