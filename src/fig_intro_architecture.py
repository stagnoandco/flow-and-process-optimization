"""fig_intro_architecture.py

Introduction figure for *Flow and Process Optimization*: the architecture of
the approach. Produced through the shared style module, no local overrides.

Read from the ground up, as a building. Governance is the footing, the two
enabling domains sit on it, and the four steps of the approach are the floors.
Every floor holds its own boxes, so the items inside a floor read as peers.
No arrows: the sequence is carried by position, the caption carries the rest.

Wording avoids "book" and "chapter" so the same figure can serve a wider
approach later.

Output: figures/fig_intro_architecture.svg + .png (300 dpi), one save call.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.patches as mpatches
import figstyle

figstyle.apply()

H = 6.9

BLUE = figstyle.BLUE
GRAY = figstyle.GRAY
FLOOR_FILL = "#DCE9F4"
FLOOR_EDGE = BLUE
BASE_FILL = "#EDEDED"
BASE_EDGE = "#B0B0B0"
FOOTING_FILL = "#E0E0E0"
INK = "#333333"

HEAD = figstyle.LABEL_SIZE + 0.5
BOX = figstyle.ANNOT_SIZE
NOTE = figstyle.ANNOT_SIZE - 0.5

GAP = 0.008
PAD = 0.012
HEADER_H = 0.040


def slab(ax, y0, h, x0, x1, fill, edge, lw=0.9, radius=0.008):
    ax.add_patch(mpatches.FancyBboxPatch(
        (x0, y0), x1 - x0, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=lw, facecolor=fill, edgecolor=edge, zorder=2))


def text(ax, x, y, s, color, size, ha="center", weight="normal",
         style="normal"):
    ax.text(x, y, s, ha=ha, va="center", fontsize=size, color=color,
            fontweight=weight, style=style, zorder=3, linespacing=1.30)


def floor(ax, y0, labels, header, box_h):
    """One floor: a header strip, then one row of boxes of equal width."""
    cols = len(labels)
    h = HEADER_H + box_h + 2 * PAD
    slab(ax, y0, h, 0.0, 1.0, FLOOR_FILL, FLOOR_EDGE)
    text(ax, PAD + 0.006, y0 + h - PAD - HEADER_H / 2, header, BLUE, HEAD,
         ha="left", weight="bold")
    inner_w = (1.0 - 2 * PAD) / cols
    for i, label in enumerate(labels):
        bx0 = PAD + i * inner_w
        slab(ax, y0 + PAD, box_h, bx0 + 0.004, bx0 + inner_w - 0.004,
             "white", FLOOR_EDGE, lw=0.7, radius=0.006)
        text(ax, bx0 + inner_w / 2, y0 + PAD + box_h / 2, label, INK, BOX)
    return y0 + h


fig, ax = figstyle.new_figure(height_in=H)
fig.subplots_adjust(left=0, right=1, top=1, bottom=0)   # axes fill the canvas
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

y = 0.012

h_foot = 0.062
slab(ax, y, h_foot, 0.0, 1.0, FOOTING_FILL, BASE_EDGE)
text(ax, 0.5, y + h_foot / 2,
     "Governance:  which flows deserve the effort,\n"
     "and which capabilities to build",
     GRAY, figstyle.LABEL_SIZE)
y += h_foot + GAP

h_dom = 0.075
half = (1.0 - 2 * PAD) / 2
slab(ax, y, h_dom, 0.0, 1.0, BASE_FILL, BASE_EDGE)
for i, label in enumerate(["Organizational change",
                           "Information systems and data"]):
    bx0 = PAD + i * half
    slab(ax, y + PAD, h_dom - 2 * PAD, bx0 + 0.004, bx0 + half - 0.004,
         "white", BASE_EDGE, lw=0.7, radius=0.006)
    text(ax, bx0 + half / 2, y + h_dom / 2, label, GRAY, BOX)
y += h_dom

text(ax, 0.5, y + 0.024,
     "what this approach rests on, and does not itself address",
     GRAY, NOTE, style="italic")
y += 0.048

y = floor(ax, y,
          ["What we\noptimize,\nand why",
           "System\ndynamics\n(Beer Game)",
           "The physics\nof flow",
           "Load,\ncapacity,\nand OEE"],
          "1    Understand flows and processes", box_h=0.088)
y += GAP

y = floor(ax, y, ["The Theory of Constraints"],
          "2    Target where we act", box_h=0.052)
y += GAP

y = floor(ax, y,
          ["Lean", "Value stream\nmapping", "Planning:\nMRP\nDDMRP",
           "Six Sigma"],
          "3    Optimize with the right lever", box_h=0.088)
y += GAP

y = floor(ax, y, ["Process mining", "Discrete-event\nsimulation"],
          "4    Model and validate the data", box_h=0.068)

# Trim the axes to the built height so the embed carries no dead white band.
top = y + 0.012
ax.set_ylim(0, top)
fig.set_size_inches(figstyle.TEXT_BLOCK_WIDTH_IN, H * top)

out = Path(__file__).resolve().parent.parent / "figures" / "fig_intro_architecture"
svg, png = figstyle.save(fig, out)
print("written:", svg, png, "top of stack:", round(y, 3))
