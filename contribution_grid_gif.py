#!/usr/bin/env python3
"""Convert a local video into an animated contribution-style pixel grid GIF.

The default output is a 53 x 7 grid. Source frames are sampled, reduced to
intensity values, and rendered as looping contribution-style squares.

The source video is read locally and is never copied by this tool. A GIF is
silent; image embedding does not carry the source video's audio.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw
except ImportError as exc:
    missing = getattr(exc, "name", "a required package")
    raise SystemExit(
        f"Missing dependency: {missing}. Install with: "
        "python -m pip install opencv-python-headless pillow"
    ) from exc


PALETTES: dict[str, list[tuple[int, int, int]]] = {
    "github": [
        (22, 27, 34),
        (14, 68, 41),
        (0, 109, 50),
        (38, 166, 65),
        (57, 211, 83),
    ],
    "mono": [
        (13, 17, 23),
        (48, 54, 61),
        (110, 118, 129),
        (201, 209, 217),
        (255, 255, 255),
    ],
    "tokyonight": [
        (26, 27, 39),
        (65, 72, 104),
        (86, 95, 137),
        (122, 162, 247),
        (187, 154, 247),
    ],
}

LEVEL_THRESHOLDS = (24, 72, 132, 196)

# A cell is a square: the crop must have the grid's aspect ratio, otherwise the
# subject is squeezed. 53 cells wide / 7 tall is a very wide letterbox, so a 4:3
# or 16:9 source has to lose vertical field of view -- crop, never squash.
FIT_MODES = ("crop", "stretch")


def build_palette(colors: Sequence[tuple[int, int, int]]) -> list[int]:
    """Return a 256-entry RGB palette suitable for Pillow P-mode images."""
    flat = [channel for color in colors for channel in color]
    return flat + [0] * (768 - len(flat))


def center_crop_box(
    frame_width: int, frame_height: int, grid_width: int, grid_height: int
) -> tuple[int, int, int, int]:
    """Return a centred, aspect-preserving crop as (x0, x1, y0, y1)."""
    if min(frame_width, frame_height, grid_width, grid_height) < 1:
        raise ValueError("Frame and grid dimensions must be positive.")
    target_ratio = grid_width / grid_height
    source_ratio = frame_width / frame_height
    if source_ratio > target_ratio:
        crop_width = max(1, min(frame_width, round(frame_height * target_ratio)))
        x0 = (frame_width - crop_width) // 2
        return x0, x0 + crop_width, 0, frame_height
    crop_height = max(1, min(frame_height, round(frame_width / target_ratio)))
    y0 = (frame_height - crop_height) // 2
    return 0, frame_width, y0, y0 + crop_height


def frame_delays_ms(frame_count: int, fps: float) -> list[int]:
    """Distribute GIF delays in centiseconds to reduce cumulative timing drift."""
    if frame_count < 1 or not np.isfinite(fps) or fps <= 0:
        raise ValueError("frame_count and fps must be positive.")
    delays = []
    for index in range(frame_count):
        current = int(round(100.0 * (index + 1) / fps))
        previous = int(round(100.0 * index / fps))
        delays.append(max(1, current - previous) * 10)
    return delays


def find_content_box(bgr_frame: np.ndarray, threshold: int = 20) -> tuple[int, int, int, int]:
    """Return (x0, x1, y0, y1) of the non-letterbox area of one frame."""
    gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
    columns = np.where(gray.max(axis=0) > threshold)[0]
    rows = np.where(gray.max(axis=1) > threshold)[0]
    if not columns.size or not rows.size:
        return 0, gray.shape[1], 0, gray.shape[0]
    return int(columns.min()), int(columns.max()) + 1, int(rows.min()), int(rows.max()) + 1


def probe_geometry(
    video: Path,
    *,
    grid_width: int,
    grid_height: int,
    probe_frames: int = 120,
) -> tuple[int, int, int, int, int]:
    """Sample the clip once to find the pillarbox and the vertical crop window.

    Returns (x0, x1, band_top, band_height, frame_height). The band keeps the
    grid aspect ratio and is centred on the temporal median of the subject's
    dark-mass centroid, so a mostly-still silhouette stays framed without any
    per-frame tracking jitter.
    """
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SystemExit(f"Error: could not open video: {video}")

    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    stride = max(1, frame_count // probe_frames) if frame_count else 1

    boxes: list[tuple[int, int]] = []
    centroids: list[float] = []
    index = 0
    sampled = 0
    try:
        while sampled < probe_frames:
            ok = capture.grab()
            if not ok:
                break
            if index % stride == 0:
                ok, frame = capture.retrieve()
                if ok:
                    x0, x1, _, _ = find_content_box(frame)
                    boxes.append((x0, x1))
                    gray = cv2.cvtColor(frame[:, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
                    mass = np.clip(gray.max() - gray, 0, None)
                    total = float(mass.sum())
                    if total > 1e-6:
                        rows = np.arange(mass.shape[0], dtype=np.float32)[:, None]
                        centroids.append(float((mass * rows).sum() / total))
                    sampled += 1
            index += 1
    finally:
        capture.release()

    if boxes:
        x0 = int(np.median([b[0] for b in boxes]))
        x1 = int(np.median([b[1] for b in boxes]))
    else:
        x0, x1 = 0, 0
    if x1 - x0 < grid_width:
        x0 = 0
        x1 = max(x1, frame_width or x1 or grid_width)
    if not frame_height:
        frame_height = 480

    content_width = x1 - x0
    band_height = int(round(content_width * grid_height / grid_width))
    band_height = max(1, min(band_height, frame_height))

    if centroids:
        center = float(np.median(centroids))
        band_top = int(round(center - band_height / 2))
    else:
        band_top = (frame_height - band_height) // 2
    band_top = max(0, min(band_top, frame_height - band_height))
    return x0, x1, band_top, band_height, frame_height


def render_frame(
    bgr_frame: np.ndarray,
    *,
    width: int,
    height: int,
    cell_size: int,
    gap: int,
    palette: Sequence[tuple[int, int, int]],
    invert: bool,
    equalize: bool,
    box: tuple[int, int, int, int] | None = None,
    fit: str = "crop",
) -> Image.Image:
    gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)

    if box is not None and fit == "crop":
        x0, x1, band_top, band_height = box
        gray = gray[band_top:band_top + band_height, x0:x1]
    elif box is not None and fit == "stretch":
        x0, x1, _, _ = box
        gray = gray[:, x0:x1]

    if equalize:
        gray = cv2.equalizeHist(gray)

    # INTER_AREA box-filters each cell, so a cell averages a square region of
    # the source. A non-uniform source ratio is never stretched into the grid.
    pixels = cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)
    if invert:
        pixels = 255 - pixels

    indices = np.digitize(pixels, LEVEL_THRESHOLDS).astype(np.uint8)

    image_width = width * cell_size + (width - 1) * gap
    image_height = height * cell_size + (height - 1) * gap
    image = Image.new("P", (image_width, image_height), color=0)
    image.putpalette(build_palette(palette))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        top = y * (cell_size + gap)
        for x in range(width):
            left = x * (cell_size + gap)
            index = int(indices[y, x])
            draw.rectangle(
                (left, top, left + cell_size - 1, top + cell_size - 1),
                fill=index,
            )
    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a video into an animated contribution-style grid GIF."
    )
    parser.add_argument("video", type=Path, help="Path to a local video file")
    parser.add_argument(
        "--output", type=Path, default=Path("contribution-grid.gif"),
        help="Output GIF path (default: ./contribution-grid.gif)",
    )
    parser.add_argument("--fps", type=float, default=8.0,
                        help="Output animation frame rate (default: 8; range 1-20)")
    parser.add_argument("--width", type=int, default=53,
                        help="Grid columns (default: 53)")
    parser.add_argument("--height", type=int, default=7,
                        help="Grid rows (default: 7)")
    parser.add_argument("--cell-size", type=int, default=10,
                        help="Square cell size in pixels (default: 10)")
    parser.add_argument("--gap", type=int, default=3,
                        help="Gap between cells in pixels (default: 3)")
    parser.add_argument("--palette", choices=tuple(PALETTES), default="github",
                        help="Cell color palette (default: github)")
    parser.add_argument("--start", type=float, default=0.0,
                        help="Start time in seconds (default: 0)")
    parser.add_argument("--duration", type=float, default=None,
                        help="Maximum output duration in seconds (default: full video)")
    parser.add_argument("--invert", action="store_true",
                        help="Invert brightness if the source has a dark subject on a light background")
    parser.add_argument("--no-equalize", action="store_true",
                        help="Disable histogram equalization")
    parser.add_argument("--fit", choices=FIT_MODES, default="crop",
                        help="crop keeps cells square and cuts field of view (default); "
                             "stretch squashes the whole frame into the grid")
    parser.add_argument("--no-autocrop", action="store_true",
                        help="Skip automatic detection; crop centrally instead (or use --fit stretch)")
    args = parser.parse_args()

    if not args.video.is_file():
        parser.error(f"Input video does not exist: {args.video}")
    if not (1.0 <= args.fps <= 20.0):
        parser.error("--fps must be between 1 and 20")
    if args.width < 1 or args.height < 1:
        parser.error("--width and --height must be positive")
    if not (2 <= args.cell_size <= 64):
        parser.error("--cell-size must be between 2 and 64")
    if not (0 <= args.gap <= 32):
        parser.error("--gap must be between 0 and 32")
    if args.start < 0 or (args.duration is not None and args.duration <= 0):
        parser.error("--start must be non-negative and --duration must be positive")
    return args


def main() -> int:
    args = parse_args()
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        print(f"Error: could not open video: {args.video}", file=sys.stderr)
        return 2

    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not np.isfinite(source_fps) or source_fps <= 0:
        capture.release()
        print("Error: video does not report a valid frame rate.", file=sys.stderr)
        return 2

    total_duration = frame_count / source_fps if frame_count > 0 else None
    if total_duration is not None and args.start >= total_duration:
        capture.release()
        print("Error: --start is beyond the end of the video.", file=sys.stderr)
        return 2

    end_time = total_duration
    if args.duration is not None:
        requested_end = args.start + args.duration
        end_time = min(requested_end, total_duration) if total_duration else requested_end

    first_frame = int(round(args.start * source_fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame)
    source_index = first_frame
    next_sample_index = float(first_frame)
    source_step = source_fps / args.fps

    frames: list[Image.Image] = []
    palette = PALETTES[args.palette]

    box = None
    if not args.no_autocrop:
        x0, x1, band_top, band_height, frame_height = probe_geometry(
            args.video, grid_width=args.width, grid_height=args.height
        )
        if args.fit == "crop":
            box = (x0, x1, band_top, band_height)
            print(
                f"Auto-crop: pillarbox {x0}..{x1} ({x1 - x0}px), "
                f"band y={band_top}..{band_top + band_height} "
                f"of {frame_height}px -> square cells, no squashing."
            )
        else:
            box = (x0, x1, 0, frame_height)
            print(
                f"Auto-crop: pillarbox {x0}..{x1} ({x1 - x0}px); "
                f"--fit {args.fit} stretches the frame into {args.width}x{args.height}."
            )
    elif args.fit == "crop":
        box = center_crop_box(
            int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            args.width,
            args.height,
        )
        print("Auto-crop disabled; using a centred aspect-preserving crop.")

    print(
        f"Reading {args.video} ({source_fps:.3f} fps); "
        f"sampling at {args.fps:g} fps into {args.width}x{args.height} cells..."
    )

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            current_time = source_index / source_fps
            if end_time is not None and current_time >= end_time:
                break

            if source_index + 1e-6 >= next_sample_index:
                frames.append(
                    render_frame(
                        frame,
                        width=args.width,
                        height=args.height,
                        cell_size=args.cell_size,
                        gap=args.gap,
                        palette=palette,
                        invert=args.invert,
                        equalize=not args.no_equalize,
                        box=box,
                        fit=args.fit,
                    )
                )
                next_sample_index += source_step

            source_index += 1
    finally:
        capture.release()

    if not frames:
        print("Error: no frames were sampled; check the input and time range.", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # GIF stores delays in centiseconds, so a fixed non-integer delay drifts.
    # Alternate the two neighbouring centisecond values to keep the mean period
    # equal to 1 / fps; otherwise 8 fps silently becomes 120 ms (8.33 fps).
    delays_ms = frame_delays_ms(len(frames), args.fps)
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=delays_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )

    actual_duration = sum(delays_ms) / 1000.0
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(
        f"Created {args.output} | {len(frames)} frames | "
        f"{actual_duration:.1f}s | {frames[0].width}x{frames[0].height}px | "
        f"{size_mb:.2f} MiB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
