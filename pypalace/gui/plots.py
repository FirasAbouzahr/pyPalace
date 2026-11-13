"""Same-canvas metal + gap plot for the GDS tagger (inspect_gds-style labels)."""

from __future__ import annotations

from typing import Any, Iterable

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from .state import GuiProject


_PALETTE = (
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
    "#86BCB6",
    "#D37295",
)
_UNTAGGED_EDGE = "#222222"
_SELECTED_EDGE = "#111111"
_PORT_COLOR = "#C0392B"
_GAP_UNTAGGED = "#D4C4E8"


def _ring_xy(coords) -> tuple[list[float], list[float]]:
    xs, ys = zip(*coords)
    return list(xs), list(ys)


def _poly_parts(geom) -> list[Polygon]:
    if isinstance(geom, Polygon):
        return [geom] if not geom.is_empty else []
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and not g.is_empty]


def _add_filled_poly(
    fig,
    poly: Polygon,
    *,
    color: str,
    opacity: float,
    line_width: float,
    line_dash: str,
    legendgroup: str,
    showlegend: bool,
    name: str,
    customdata_row: list[Any],
):
    import plotly.graph_objects as go

    x, y = _ring_xy(poly.exterior.coords)
    n = len(x)
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            fill="toself",
            fillcolor=color,
            opacity=opacity,
            line=dict(color=_UNTAGGED_EDGE, width=line_width, dash=line_dash),
            name=name,
            legendgroup=legendgroup,
            showlegend=showlegend,
            mode="lines",
            hovertemplate=f"{name}<br>x=%{{x:.4g}}<br>y=%{{y:.4g}}<extra></extra>",
            customdata=[customdata_row] * n,
        )
    )
    for hole in poly.interiors:
        hx, hy = _ring_xy(hole.coords)
        fig.add_trace(
            go.Scatter(
                x=hx,
                y=hy,
                fill="toself",
                fillcolor="rgba(255,255,255,0.95)",
                line=dict(color="#222222", width=0.5),
                legendgroup=legendgroup,
                showlegend=False,
                mode="lines",
                hoverinfo="skip",
            )
        )


def _label_anchors(
    draw_polys: list[Polygon],
    *,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
) -> list[tuple[float, float, float, float]]:
    """inspect_gds-style NE anchors + collision-aware text positions."""
    xspan = max(xmax - xmin, 1e-12)
    yspan = max(ymax - ymin, 1e-12)
    dx = 0.035 * xspan
    dy = 0.035 * yspan
    min_sep = 0.04 * max(xspan, yspan)
    occupied: list[tuple[float, float]] = []
    out: list[tuple[float, float, float, float]] = [(0.0, 0.0, 0.0, 0.0)] * len(draw_polys)

    for i in sorted(range(len(draw_polys)), key=lambda k: draw_polys[k].area, reverse=True):
        p = draw_polys[i]
        minx_p, miny_p, maxx_p, maxy_p = p.bounds
        anchor_x, anchor_y = float(maxx_p), float(maxy_p)
        if not p.intersects(ShapelyPoint(anchor_x, anchor_y)):
            nearest = p.exterior.interpolate(
                p.exterior.project(ShapelyPoint(anchor_x, anchor_y))
            )
            anchor_x, anchor_y = float(nearest.x), float(nearest.y)

        text_x = anchor_x + dx
        text_y = anchor_y + dy
        for _ in range(12):
            conflict = False
            for ox, oy in occupied:
                if (text_x - ox) ** 2 + (text_y - oy) ** 2 < min_sep**2:
                    text_y += 0.6 * min_sep
                    conflict = True
                    break
            if not conflict:
                break
        occupied.append((text_x, text_y))
        out[i] = (anchor_x, anchor_y, text_x, text_y)
    return out


def build_tag_figure(
    project: GuiProject,
    *,
    highlight_polys: Iterable[int] | None = None,
    highlight_gaps: Iterable[int] | None = None,
    show_gaps: bool = True,
    show_metals: bool = True,
    show_ports: bool = True,
    port_corner: tuple[float, float] | None = None,
):
    """Plot metals/gaps/ports; clickable markers carry selection customdata."""
    import plotly.graph_objects as go

    fig = go.Figure()
    hi_p = set(int(i) for i in (highlight_polys or []))
    hi_g = set(int(i) for i in (highlight_gaps or []))

    poly_owner: dict[int, str] = {}
    for name, tag in project.surfaces.items():
        for pid in tag.polygons:
            poly_owner[pid] = name
    gap_owner: dict[int, str] = {}
    for name, tag in project.gaps.items():
        for gid in tag.gaps:
            gap_owner[gid] = name

    # Bounds for label layout
    all_bounds: list[tuple[float, float, float, float]] = []
    if show_metals:
        all_bounds.extend(p.bounds for p in project.polygons)
    if show_gaps:
        all_bounds.extend(g.bounds for g in project.gap_pieces)
    if show_ports:
        for port in project.ports.values():
            all_bounds.append(port.as_polygon().bounds)
    if not all_bounds:
        fig.update_layout(title="Load a GDS to begin", height=700)
        return fig

    full_xmin = min(b[0] for b in all_bounds)
    full_ymin = min(b[1] for b in all_bounds)
    full_xmax = max(b[2] for b in all_bounds)
    full_ymax = max(b[3] for b in all_bounds)
    pad = 0.02 * max(full_xmax - full_xmin, full_ymax - full_ymin, 1e-9)
    xmin, xmax = full_xmin - pad, full_xmax + pad
    ymin, ymax = full_ymin - pad, full_ymax + pad

    annotations: list[dict] = []
    shown_legend: set[str] = set()

    # --- metals (largest first, like inspect_gds) ---
    if show_metals and project.polygons:
        order = sorted(
            range(len(project.polygons)),
            key=lambda i: project.polygons[i].area,
            reverse=True,
        )
        anchors = _label_anchors(project.polygons, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
        for pid in order:
            poly = project.polygons[pid]
            owner = poly_owner.get(pid)
            color = _PALETTE[pid % len(_PALETTE)]
            selected = pid in hi_p
            opacity = 0.75 if selected else 0.55
            lw = 2.2 if selected else 0.6
            label = f"p{pid}" + (f" · {owner}" if owner else "")
            lg = f"metal:{owner}" if owner else "metal:untagged"
            showleg = lg not in shown_legend
            if showleg:
                shown_legend.add(lg)
            for part in _poly_parts(poly):
                _add_filled_poly(
                    fig,
                    part,
                    color=color,
                    opacity=opacity,
                    line_width=lw,
                    line_dash="solid",
                    legendgroup=lg,
                    showlegend=showleg,
                    name=label,
                    customdata_row=["poly", pid],
                )
                showleg = False

            ax_, ay_, tx, ty = anchors[pid]
            annotations.append(
                dict(
                    x=tx,
                    y=ty,
                    ax=ax_,
                    ay=ay_,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    text=f"<b>p{pid}</b>",
                    showarrow=True,
                    arrowhead=2,
                    arrowwidth=1.2,
                    arrowcolor=color,
                    font=dict(size=11, color=color, family="IBM Plex Mono, monospace"),
                    bgcolor="rgba(255,255,255,0.92)",
                    bordercolor=color,
                    borderwidth=1.2,
                    borderpad=3,
                    align="left",
                )
            )
            # Click target at the inspect_gds-style anchor dot
            fig.add_trace(
                go.Scatter(
                    x=[ax_],
                    y=[ay_],
                    mode="markers",
                    marker=dict(
                        size=14 if selected else 10,
                        color=color,
                        line=dict(color="black", width=0.8),
                        symbol="circle",
                    ),
                    name=f"pick-p{pid}",
                    showlegend=False,
                    hovertemplate=f"<b>p{pid}</b>"
                    + (f" · {owner}" if owner else "")
                    + "<br>click to select<extra></extra>",
                    customdata=[["poly", pid]],
                )
            )

    # --- gaps ---
    if show_gaps and project.gap_pieces:
        # Faint metal outlines already drawn; gaps overlaid dotted
        anchors_g = _label_anchors(
            project.gap_pieces, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax
        )
        for gid, gap in enumerate(project.gap_pieces):
            owner = gap_owner.get(gid)
            color = _PALETTE[(gid + 3) % len(_PALETTE)] if owner else _GAP_UNTAGGED
            selected = gid in hi_g
            opacity = 0.65 if selected else 0.35
            lw = 2.0 if selected else 0.7
            label = f"g{gid}" + (f" · {owner}" if owner else "")
            lg = f"gap:{owner}" if owner else "gap:untagged"
            showleg = lg not in shown_legend
            if showleg:
                shown_legend.add(lg)
            for part in _poly_parts(gap):
                _add_filled_poly(
                    fig,
                    part,
                    color=color,
                    opacity=opacity,
                    line_width=lw,
                    line_dash="dot",
                    legendgroup=lg,
                    showlegend=showleg,
                    name=label,
                    customdata_row=["gap", gid],
                )
                showleg = False
            ax_, ay_, tx, ty = anchors_g[gid]
            annotations.append(
                dict(
                    x=tx,
                    y=ty,
                    ax=ax_,
                    ay=ay_,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    text=f"<b>g{gid}</b>",
                    showarrow=True,
                    arrowhead=2,
                    arrowwidth=1.0,
                    arrowcolor=color,
                    font=dict(size=11, color="#4A148C", family="IBM Plex Mono, monospace"),
                    bgcolor="rgba(255,255,255,0.92)",
                    bordercolor=color,
                    borderwidth=1.2,
                    borderpad=3,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[ax_],
                    y=[ay_],
                    mode="markers",
                    marker=dict(
                        size=14 if selected else 10,
                        color=color,
                        symbol="diamond",
                        line=dict(color="#4A148C", width=0.8),
                    ),
                    name=f"pick-g{gid}",
                    showlegend=False,
                    hovertemplate=f"<b>g{gid}</b>"
                    + (f" · {owner}" if owner else "")
                    + "<br>click to select<extra></extra>",
                    customdata=[["gap", gid]],
                )
            )

    # --- ports ---
    if show_ports:
        for port in project.ports.values():
            box = port.as_polygon()
            x, y = _ring_xy(box.exterior.coords)
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    fill="toself",
                    fillcolor=_PORT_COLOR,
                    opacity=0.45,
                    line=dict(color=_PORT_COLOR, width=2),
                    name=f"port:{port.name}",
                    legendgroup="ports",
                    showlegend=True,
                    mode="lines",
                    hovertemplate=f"port <b>{port.name}</b><br>"
                    + f"dir={port.direction} R={port.R}<extra></extra>",
                    customdata=[["port", port.name]] * len(x),
                )
            )
            c = box.centroid
            annotations.append(
                dict(
                    x=float(c.x),
                    y=float(c.y),
                    text=f"<b>{port.name}</b>",
                    showarrow=False,
                    font=dict(size=11, color=_PORT_COLOR),
                    bgcolor="rgba(255,255,255,0.9)",
                    bordercolor=_PORT_COLOR,
                    borderwidth=1,
                )
            )

    if port_corner is not None:
        fig.add_trace(
            go.Scatter(
                x=[port_corner[0]],
                y=[port_corner[1]],
                mode="markers",
                marker=dict(size=14, color=_PORT_COLOR, symbol="x"),
                name="port corner 1",
                showlegend=False,
                hovertemplate="port corner 1<extra></extra>",
            )
        )

    fig.update_layout(
        title="Click ● metal / ◆ gap markers to select · draw ports with two clicks",
        xaxis=dict(title="x", range=[xmin, xmax], scaleanchor="y", scaleratio=1, constrain="domain"),
        yaxis=dict(title="y", range=[ymin, ymax]),
        annotations=annotations,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        margin=dict(l=40, r=160, t=50, b=40),
        height=720,
        clickmode="event+select",
        dragmode="pan",
        plot_bgcolor="#FAFAFA",
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
    for name, port in project.ports.items():
        rows.append(
            {
                "kind": "port",
                "name": name,
                "ids": [round(port.xmin, 3), round(port.ymin, 3), round(port.xmax, 3), round(port.ymax, 3)],
                "attr": port.attr,
                "union": None,
                "n_pieces": 1,
            }
        )
    return pd.DataFrame(rows)


def parse_plotly_selection(selection_state) -> list[tuple[str, Any]]:
    """Extract (kind, id) pairs from a Streamlit Plotly selection event."""
    hits: list[tuple[str, Any]] = []
    if selection_state is None:
        return hits
    points = getattr(selection_state, "selection", selection_state)
    if hasattr(points, "points"):
        points = points.points
    elif isinstance(points, dict):
        points = points.get("points", [])
    if not points:
        return hits
    for pt in points:
        cd = None
        if isinstance(pt, dict):
            cd = pt.get("customdata")
        else:
            cd = getattr(pt, "customdata", None)
        if cd is None:
            continue
        # customdata may be ["poly", 3] or nested
        if isinstance(cd, (list, tuple)) and len(cd) >= 2:
            kind, ident = cd[0], cd[1]
            hits.append((str(kind), ident))
    return hits
