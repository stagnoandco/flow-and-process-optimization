# book_style/figstyle.py
"""Figure style module for *Demand Analysis and Segmentation*.

Single source encoding FIGURE_STYLE_SHEET v1.1 (frozen). Every book figure
is produced through this module; no per-figure style overrides.

v1.1 rules encoded here:
  - No in-figure title: the caption below the figure carries the message.
    ax.set_title is reserved for short bold per-panel labels in panel grids.
  - SVG is the deliverable figure format; a 300 dpi PNG is written alongside
    as the docx embed fallback. One save() call writes both.

Usage:
    from book_style import figstyle
    fig, ax = figstyle.new_figure(height_in=2.4)
    ... plot with figstyle.BLUE / ORANGE ...
    figstyle.style_bar_axes(ax)          # or style_line_axes(ax)
    figstyle.save(fig, "figures/fig_2_2")   # writes fig_2_2.svg + fig_2_2.png
"""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

# ------------------------------------------------------------
# Geometry (style sheet section 1)
# ------------------------------------------------------------
TEXT_BLOCK_WIDTH_IN = 4.51     # measured on the published Flow book
DEFAULT_HEIGHT_IN = 2.4
MAX_HEIGHT_IN = 7.5
EXPORT_DPI = 300

# ------------------------------------------------------------
# Palette (style sheet section 2): tab10 primaries, semantic green/red
# ------------------------------------------------------------
BLUE = "#1F77B4"       # primary series
ORANGE = "#FF7F0E"     # secondary series / contrast
GREEN = "#2CA02C"      # semantic only: target met, OK zone, useful value
RED = "#D62728"        # semantic only: loss, constraint, out-of-spec
AMBER = "#D4A017"      # intermediate zone (buffer figures)
GRAY = "#7F7F7F"       # reference lines, annotations
GRID = "#CCCCCC"

SERIES_CYCLE = [BLUE, ORANGE, GRAY]

# Fonts (DejaVu Sans). Sizes recalibrated on Antonio's published-figure
# standard (July 2026): at the final 4.5 in embed width, effective print
# sizes sit near 7-8 pt, as in the Flow book. Style sheet amendment to
# v1.2 pending Antonio's ratification.
TITLE_SIZE = 9     # panel labels only (no figure-level title)
LABEL_SIZE = 8
TICK_SIZE = 7
ANNOT_SIZE = 7


def apply() -> None:
    """Set global rcParams. Call once per figure-producing script."""
    matplotlib.rcParams.update({
        "figure.figsize": (TEXT_BLOCK_WIDTH_IN, DEFAULT_HEIGHT_IN),
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "font.family": "sans-serif",
        "axes.titlesize": TITLE_SIZE,
        "axes.titleweight": "bold",
        "axes.labelsize": LABEL_SIZE,
        "xtick.labelsize": TICK_SIZE,
        "ytick.labelsize": TICK_SIZE,
        "legend.fontsize": ANNOT_SIZE,
        "legend.frameon": True,
        "legend.framealpha": 1.0,
        "legend.edgecolor": GRID,
        "grid.color": GRID,
        "grid.linestyle": "--",
        "grid.linewidth": 0.6,
        "lines.linewidth": 1.5,
        "axes.prop_cycle": matplotlib.cycler(color=SERIES_CYCLE),
    })


def new_figure(height_in: float = DEFAULT_HEIGHT_IN, ncols: int = 1,
               nrows: int = 1):
    """A figure at text-block width. Height capped at MAX_HEIGHT_IN."""
    if height_in > MAX_HEIGHT_IN:
        raise ValueError(f"height {height_in} in exceeds the {MAX_HEIGHT_IN} in cap")
    apply()
    return plt.subplots(nrows, ncols,
                        figsize=(TEXT_BLOCK_WIDTH_IN, height_in))


def style_bar_axes(ax) -> None:
    """Bar charts: horizontal gridlines only, no top/right spines."""
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def style_line_axes(ax) -> None:
    """Line charts: light full frame, gridlines both directions allowed."""
    ax.grid(True)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(GRID)


def add_value_labels(ax, fmt: str = "{:.0f}") -> None:
    """Bold value labels above bars."""
    for container in ax.containers:
        ax.bar_label(container, fmt=fmt, fontweight="bold",
                     fontsize=ANNOT_SIZE, padding=2)


def annotate(ax, text: str, xy, xytext) -> None:
    """One thin-arrow annotation, style-sheet compliant (max two per figure)."""
    ax.annotate(text, xy=xy, xytext=xytext, fontsize=ANNOT_SIZE, color=GRAY,
                ha="center",
                arrowprops={"arrowstyle": "->", "color": GRAY, "linewidth": 0.8})


def save(fig, path: str | Path) -> tuple[Path, Path]:
    """Export SVG (deliverable) and 300 dpi PNG (docx embed fallback).

    One call writes both, per style sheet v1.1 section 1. `path` may carry
    a .svg or .png extension or none; the stem is used for both files.
    Returns (svg_path, png_path)."""
    path = Path(path)
    stem = path.with_suffix("")
    stem.parent.mkdir(parents=True, exist_ok=True)
    svg_path = stem.with_suffix(".svg")
    png_path = stem.with_suffix(".png")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    fig.savefig(png_path, dpi=EXPORT_DPI, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    return svg_path, png_path
