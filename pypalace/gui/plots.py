"""Same-canvas metal + gap plot for the GDS tagger."""

from __future__ import annotations

from typing import Iterable

import numpy as np
from shapely.geometry import MultiPolygon, Polygon

from .state import GuiProject


_METAL_COLORS = (
    "#4E79A7",
    "#F28E2B",
    "#E15759",
    "#76B7B2",
    "#59A14F",
    "#EDC948",
    "#B07AA1",
    "#FF9DA7",
    "#9C755F",
    "#BAB0AC",
)
_GAP_COLOR = "#6B5B95"
_UNTAGGED_METAL = "#C7C7C7"
_UNTAGGED_GAP = "#D4C4E8"


def _ring_xy(coords) -> tuple[list[float], list[float]]:
    xs, ys = zip(*coords)
    return list(xs), list(ys)


def _add_polygon_trace(fig, poly: Polygon, *, name: str, color: str, opacity: float, legendgroup: str, showlegend: bool, customdata: dict, line_dash: str = "solid"):
    import plotly.graph_objects as go

    if poly.is_empty or poly.area <= 0:
        return
    x, y = _ring_xy(poly.exterior.coords)
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            fill="toself",
            fillcolor=color,
            opacity=opacity,
            line=dict(color="#222222", width=1, dash=line_dash),
            name=name,
            legendgroup=legendgroup,
            showlegend=showlegend,
            mode="lines",
            hovertemplate=(
                f"{name}<br>"
                + "x=%{x:.4g}<br>y=%{y:.4g}<extra></extra>"
            ),
            customdata=[customdata],
        )
    )
    # Holes as white cutouts (visual only)
    for hole in poly.interiors:
        hx, hy = _ring_xy(hole.coords)
        fig.add_trace(
            go.Scatter(
                x=hx,
                y=hy,
                fill="toself",
                fillcolor="rgba(255,255,255,0.95)",
                line=dict(color="#222222", width=0.5),
                name=name,
                legendgroup=legendgroup,
                showlegend=False,
                mode="lines",
                hoverinfo="skip",
            )
        )


def build_tag_figure(
    project: GuiProject,
    *,
    highlight_polys: Iterable[int] | None = None,
    highlight_gaps: Iterable[int] | None = None,
    show_gaps: bool = True,
    show_metals: bool = True,
):
    """Plot metals and gaps on one canvas; tagged groups share colors."""
    import plotly.graph_objects as go

    fig = go.Figure()
    hi_p = set(int(i) for i in (highlight_polys or []))
    hi_g = set(int(i) for i in (highlight_gaps or []))

    # Map poly/gap id → tag name
    poly_owner: dict[int, str] = {}
    for name, tag in project.surfaces.items():
        for pid in tag.polygons:
            poly_owner[pid] = name
    gap_owner: dict[int, str] = {}
    for name, tag in project.gaps.items():
        for gid in tag.gaps:
            gap_owner[gid] = name

    name_color: dict[str, str] = {}
    for i, name in enumerate(project.surfaces):
        name_color[name] = _METAL_COLORS[i % len(_METAL_COLORS)]
    for i, name in enumerate(project.gaps):
        name_color[name] = _GAP_COLOR

    shown_legend: set[str] = set()

    if show_metals:
        for pid, poly in enumerate(project.polygons):
            owner = poly_owner.get(pid)
            if owner:
                color = name_color[owner]
                label = f"p{pid} · {owner}"
                lg = f"metal:{owner}"
                showleg = owner not in shown_legend
                if showleg:
                    shown_legend.add(owner)
            else:
                color = _UNTAGGED_METAL
                label = f"p{pid}"
                lg = "metal:untagged"
                showleg = "metal:untagged" not in shown_legend
                if showleg:
                    shown_legend.add("metal:untagged")
            opacity = 0.85 if pid in hi_p else 0.45
            parts = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
            for part in parts:
                _add_polygon_trace(
                    fig,
                    part,
                    name=label if showleg else label,
                    color=color,
                    opacity=opacity,
                    legendgroup=lg,
                    showlegend=showleg,
                    customdata={"kind": "poly", "id": pid, "tag": owner},
                )
                showleg = False

    if show_gaps:
        for gid, gap in enumerate(project.gap_pieces):
            owner = gap_owner.get(gid)
            if owner:
                color = name_color.get(owner, _GAP_COLOR)
                label = f"g{gid} · {owner}"
                lg = f"gap:{owner}"
                showleg = owner not in shown_legend
                if showleg:
                    shown_legend.add(owner)
            else:
                color = _UNTAGGED_GAP
                label = f"g{gid}"
                lg = "gap:untagged"
                showleg = "gap:untagged" not in shown_legend
                if showleg:
                    shown_legend.add("gap:untagged")
            opacity = 0.7 if gid in hi_g else 0.35
            parts = [gap] if isinstance(gap, Polygon) else list(getattr(gap, "geoms", [gap]))
            for part in parts:
                if not isinstance(part, Polygon):
                    continue
                _add_polygon_trace(
                    fig,
                    part,
                    name=label,
                    color=color,
                    opacity=opacity,
                    legendgroup=lg,
                    showlegend=showleg,
                    customdata={"kind": "gap", "id": gid, "tag": owner},
                    line_dash="dot",
                )
                showleg = False

    # Centroid labels for clarity
    annotations = []
    if show_metals:
        for pid, poly in enumerate(project.polygons):
            c = poly.centroid
            annotations.append(
                dict(
                    x=float(c.x),
                    y=float(c.y),
                    text=f"p{pid}",
                    showarrow=False,
                    font=dict(size=10, color="#111"),
                )
            )
    if show_gaps:
        for gid, gap in enumerate(project.gap_pieces):
            c = gap.centroid
            annotations.append(
                dict(
                    x=float(c.x),
                    y=float(c.y),
                    text=f"g{gid}",
                    showarrow=False,
                    font=dict(size=10, color="#4A148C"),
                )
            )

    fig.update_layout(
        title="GDS metals (solid) + gaps (dotted) — same canvas",
        xaxis=dict(title="x", scaleanchor="y", scaleratio=1),
        yaxis=dict(title="y"),
        annotations=annotations,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        margin=dict(l=40, r=180, t=50, b=40),
        height=700,
        clickmode="event+select",
        dragmode="pan",
    )
    return fig


def summary_table(project: GuiProject):
    import pandas as pd

    rows = []
    for name, tag in project.surfaces.items():
        rows.append(
            {
                "kind": "metal",
                "name": name,
                "ids": tag.polygons,
                "attr": tag.attr,
                "union": tag.union,
                "n_pieces": len(tag.polygons),
            }
        )
    for name, tag in project.gaps.items():
        rows.append(
            {
                "kind": "gap",
                "name": name,
                "ids": tag.gaps,
                "attr": tag.attr,
                "union": None,
                "n_pieces": len(tag.gaps),
            }
        )
    return pd.DataFrame(rows)
