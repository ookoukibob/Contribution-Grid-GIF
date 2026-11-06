import numpy as np
import pytest

from contribution_grid_gif import (
    PALETTES,
    build_palette,
    center_crop_box,
    find_content_box,
    frame_delays_ms,
    render_frame,
)


def test_palette_is_pillow_compatible():
    palette = build_palette(PALETTES["mono"])
    assert len(palette) == 768
    assert palette[:15] == [
        channel for color in PALETTES["mono"] for channel in color
    ]


def test_find_content_box_ignores_black_side_bars():
    frame = np.zeros((40, 60, 3), dtype=np.uint8)
    frame[5:35, 8:52] = 255
    assert find_content_box(frame) == (8, 52)


def test_find_content_box_falls_back_to_full_width_for_black_frame():
    frame = np.zeros((24, 48, 3), dtype=np.uint8)
    assert find_content_box(frame) == (0, 48)


def test_wide_grid_center_crop_has_square_cell_geometry():
    crop = center_crop_box(636, 480, 53, 7)
    assert crop == (0, 636, 198, 282)
    assert crop[1] - crop[0] == 636
    assert crop[3] - crop[2] == 84


def test_portrait_video_crops_horizontally_without_distortion():
    x0, x1, y0, y1 = center_crop_box(480, 852, 53, 7)
    assert y0 == 0
    assert y1 == 852
    assert (x1 - x0) / (y1 - y0) == pytest.approx(53 / 7)


def test_gif_delays_preserve_average_fps():
    delays = frame_delays_ms(80, 8)
    assert set(delays).issubset({120, 130})
    assert sum(delays) == 10_000


def test_gif_delays_reject_invalid_fps():
    with pytest.raises(ValueError):
        frame_delays_ms(10, 0)


def test_render_frame_has_expected_canvas_size():
    frame = np.zeros((84, 636, 3), dtype=np.uint8)
    rendered = render_frame(
        frame,
        width=53,
        height=7,
        cell_size=10,
        gap=3,
        palette=PALETTES["mono"],
        invert=False,
        equalize=False,
        box=(0, 636, 0, 84),
        fit="crop",
    )
    assert rendered.size == (686, 88)
    assert rendered.mode == "P"
