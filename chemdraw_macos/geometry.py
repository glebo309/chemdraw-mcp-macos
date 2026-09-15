"""Bounding-box helpers adapted from live-chemdraw-mcp (MIT).

Copyright (c) 2026 Michael Leitch.
Source: a9cebc6cf61e4d9b019463019626684fdf30beb6,
chemdraw_connector/domain/layout_math.py. Full notice: licenses/live-chemdraw-mcp.txt.
"""
from dataclasses import dataclass


@dataclass
class Box:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def center(self):
        return ((self.left + self.right) / 2, (self.top + self.bottom) / 2)


def find_overlaps(boxes, ids=None, tolerance=1.0):
    """Return pairs whose boxes overlap by more than tolerance points."""
    hits = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ox = min(a.right, b.right) - max(a.left, b.left)
            oy = min(a.bottom, b.bottom) - max(a.top, b.top)
            if ox > tolerance and oy > tolerance:
                hits.append((ids[i], ids[j]) if ids else (i, j))
    return hits


def grid_positions(boxes, columns, start_x=36., start_y=36., h_gap=18., v_gap=24.):
    """Uniform cells, adapted from the pinned upstream grid_positions.

    Caller validates columns and measured compound-plus-caption extents.
    """
    cell_w=max(b.width for b in boxes)
    cell_h=max(b.height for b in boxes)
    out=[]
    for i,box in enumerate(boxes):
        row,col=divmod(i,columns)
        cx=start_x+col*(cell_w+h_gap)+cell_w/2.
        cy=start_y+row*(cell_h+v_gap)+cell_h/2.
        out.append((cx-box.width/2.,cy-box.height/2.))
    return out
