# Contribution Grid GIF

Convert a local video into an animated GIF made from GitHub-contribution-style
squares. Frames are sampled, reduced to a grid of intensity values, and
rendered as a looping GIF.

This is an ordinary animated image generator. It does not create Git commits,
modify contribution history, or require visitors to run a browser script.

## Features

- Configurable grid dimensions (default: 53 × 7).
- Aspect-preserving crop mode, with optional side-bar detection and stable
  framing based on the clip's median dark-pixel centroid.
- Optional stretch mode when you prefer to fill the whole grid.
- GitHub, monochrome, and Tokyo Night palettes.
- Adjustable FPS, cell size, spacing, start time, and duration.
- GIF frame delays distributed in centiseconds to reduce timing drift.
- Processes a local video file; the source is never copied by this tool.

## Install

Python 3.10 or newer is recommended.

```bash
python -m pip install -e .
```

For development and tests:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Quick start

```bash
contribution-grid-gif "input.mp4" \
  --output "contribution-grid.gif" \
  --fps 8 \
  --palette github
```

The equivalent module command is:

```bash
python -m contribution_grid_gif "input.mp4" --output "contribution-grid.gif"
```

### Monochrome 53 × 7 example

```bash
contribution-grid-gif "bad_apple.mp4" \
  --output "assets/bad-apple-contribution.gif" \
  --fps 8 \
  --palette mono
```

## Options

| Option | Default | Description |
|---|---:|---|
| `--output` | `contribution-grid.gif` | Destination GIF path |
| `--fps` | `8` | Output frame rate; supported range is 1–20 |
| `--width` | `53` | Number of grid columns |
| `--height` | `7` | Number of grid rows |
| `--cell-size` | `10` | Square cell size in pixels |
| `--gap` | `3` | Gap between cells in pixels |
| `--palette` | `github` | `github`, `mono`, or `tokyonight` |
| `--start` | `0` | Start time in seconds |
| `--duration` | Full clip | Maximum segment duration in seconds |
| `--fit` | `crop` | `crop` preserves aspect ratio; `stretch` distorts to fill |
| `--no-autocrop` | Off | Skip border/subject detection; crop centrally instead |
| `--invert` | Off | Invert image brightness |
| `--no-equalize` | Off | Disable per-frame histogram equalization |

## Cropping

The default `--fit crop` mode preserves the source aspect ratio rather than
squashing the whole frame into a very wide grid. With automatic cropping
enabled, the tool samples the clip to detect vertical side bars and estimates
a stable vertical crop position from the temporal median of dark-pixel
centroids. This is particularly useful for high-contrast silhouette footage.

Use `--no-autocrop` to skip detection and take a centered, aspect-preserving
crop. Use `--fit stretch` only when you explicitly prefer the whole detected
frame over undistorted proportions.

A 53 × 7 grid is extremely wide (about 7.57:1), so crop mode necessarily
discards much of the vertical field of view from conventional video. Increase
`--height` for a taller grid with less cropping.

## Embed the GIF in a GitHub Profile README

Commit the generated GIF to a repository, then reference it from the README:

```html
<div align="center">
  <img src="assets/contribution-grid.gif"
       alt="Video rendered as an animated contribution grid"
       width="100%">
</div>
```

GitHub displays the animation to visitors as an ordinary README image. GIFs
are silent; embedding an image does not include the source video's audio.

## Media rights

This project licenses **the generator code** under the MIT License. It does
not grant rights to input video visuals or soundtracks, or to GIFs derived
from third-party media. You are responsible for obtaining any permissions
needed before publishing generated output. No video, audio, or example GIF is
bundled with this repository.

## License

[MIT](LICENSE)
