"""
GDS inspection and MeshWell-backed meshing for Palace workflows.

This module implements the GDS path:

1. :func:`inspect_gds` — plot polygons with stable ids and return a DataFrame
2. :func:`validate_surface_map` / SurfaceMap dict — name → polygon ids + attr
3. :func:`mesh_gds` — MeshWell CAD/mesh with auto ``substrate``, ``air``,
   ``far_field`` tags (no auto ground plane)

Default units are **micrometers (µm)** with ``mesh_scale=1`` (Palace
``L0 = 1e-6``).

Requires ``meshwell`` and ``gdstk`` (core package dependencies).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from shapely.affinity import scale as shapely_scale
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union


def _require_meshwell():
    try:
        import gdstk  # noqa: F401
        from meshwell.cad_occ import cad_occ
        from meshwell.model import ModelManager
        from meshwell.polyprism import PolyPrism
    except ImportError as e:
        raise ImportError(
            "GDS meshing requires 'meshwell' and 'gdstk'. "
            "Reinstall pypalace (or: pip install meshwell gdstk)."
        ) from e
    return cad_occ, ModelManager, PolyPrism


def _gmsh_add_polygon_surface_xy(gmsh, polygon: Polygon, z: float, lc: float) -> int:
    """Add a simple OCC plane surface from a Shapely polygon (line edges only)."""
    from .meshing import Mesh

    return Mesh._gmsh_add_polygon_surface(
        gmsh,
        polygon,
        z=float(z),
        lc=float(lc),
        boundary_simplify=None,
    )


def _flatten_polygons(geom) -> list[Polygon]:
    """Return individual non-empty Polygon objects from a Shapely geometry."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom] if not geom.is_empty else []
    if isinstance(geom, MultiPolygon):
        return [p for p in geom.geoms if not p.is_empty]
    if hasattr(geom, "geoms"):
        out: list[Polygon] = []
        for g in geom.geoms:
            out.extend(_flatten_polygons(g))
        return out
    return []


def _dedupe_ring(coords, tol: float) -> list[tuple[float, float]]:
    """Drop consecutive near-duplicate vertices; keep a closed ring if possible."""
    if not coords:
        return []
    pts = [(float(x), float(y)) for x, y in coords]
    # Drop closing duplicate for processing
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    cleaned: list[tuple[float, float]] = []
    for x, y in pts:
        if not cleaned:
            cleaned.append((x, y))
            continue
        if abs(x - cleaned[-1][0]) <= tol and abs(y - cleaned[-1][1]) <= tol:
            continue
        cleaned.append((x, y))
    if len(cleaned) >= 3:
        if abs(cleaned[0][0] - cleaned[-1][0]) > tol or abs(cleaned[0][1] - cleaned[-1][1]) > tol:
            cleaned.append(cleaned[0])
        elif cleaned[0] != cleaned[-1]:
            cleaned.append(cleaned[0])
    return cleaned


def _clean_polygon(poly: Polygon, snap: float | None = None) -> list[Polygon]:
    """
    Repair GDS polygons that commonly break OpenCASCADE wires.

    - make_valid / buffer(0)
    - remove duplicate consecutive vertices
    - optional grid snap via shapely.set_precision
    - enforce exterior CCW / hole CW orientation
    """
    import shapely
    from shapely import make_valid
    from shapely.geometry.polygon import orient

    if poly is None or poly.is_empty:
        return []

    geom = poly
    if not geom.is_valid:
        try:
            geom = make_valid(geom)
        except Exception:
            geom = geom.buffer(0)

    cleaned: list[Polygon] = []
    for p in _flatten_polygons(geom):
        if p.is_empty or p.area <= 0:
            continue
        # Local tolerance from polygon size if snap not provided
        minx, miny, maxx, maxy = p.bounds
        span = max(maxx - minx, maxy - miny, 1e-12)
        tol = float(snap) if snap != None else max(1e-12, 1e-9 * span)

        ext = _dedupe_ring(list(p.exterior.coords), tol)
        if len(ext) < 4:
            continue
        holes = []
        for interior in p.interiors:
            hole = _dedupe_ring(list(interior.coords), tol)
            if len(hole) >= 4:
                holes.append(hole)
        try:
            q = Polygon(ext, holes)
        except Exception:
            continue
        if not q.is_valid:
            q = q.buffer(0)
        if snap != None and snap > 0:
            try:
                q = shapely.set_precision(q, grid_size=float(snap), mode="pointwise")
            except Exception:
                pass
        for r in _flatten_polygons(q):
            if r.is_empty or r.area <= 0:
                continue
            try:
                r = orient(r, sign=1.0)
            except Exception:
                pass
            cleaned.append(r)
    return cleaned


def _drop_covered_holes(geom, others, cover_frac: float = 0.5) -> Any:
    """
    Drop holes that are already represented by other SurfaceMap metals.

    GDS ground planes often include cutouts that nearly match island polygons.
    Emitting both the hole wire and the island PolySurface creates coincident
    OpenCASCADE edges that frequently fail with ``Could not fix wire``.
    """
    parts: list[Polygon] = []
    others_ok = others is not None and not getattr(others, "is_empty", True)
    for p in _flatten_polygons(geom):
        if not p.interiors or not others_ok:
            parts.append(p)
            continue
        keep_holes = []
        for interior in p.interiors:
            hole = Polygon(interior)
            if hole.is_empty or hole.area <= 0:
                continue
            covered = hole.intersection(others)
            covered_area = float(getattr(covered, "area", 0.0) or 0.0)
            if covered_area >= cover_frac * float(hole.area):
                continue
            keep_holes.append(interior)
        parts.append(Polygon(list(p.exterior.coords), keep_holes))
    if not parts:
        return geom
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def load_gds_polygons(
    gds_file: str | Path,
    layer: tuple[int, int] = (1, 0),
    cell_name: str | None = None,
) -> list[Polygon]:
    """
    Load polygons from a GDS layer as a stable-ordered list.

    Polygons are kept separate (not unioned), so overlapping shapes such as a
    JJ on an island remain distinct for SurfaceMap tagging. Order is by
    (centroid_x, centroid_y, area) so ids stay stable across reloads.
    """
    import gdstk
    from shapely.geometry import Polygon as ShapelyPolygon

    # Ensure meshwell/gdstk are importable early for a clear error message.
    _require_meshwell()

    library = gdstk.read_gds(str(gds_file))
    if cell_name:
        cell = next((c for c in library.cells if c.name == cell_name), None)
        if cell is None:
            raise ValueError(f"Cell {cell_name!r} not found in {gds_file}")
    else:
        tops = library.top_level()
        if not tops:
            raise ValueError(f"No top-level cell found in {gds_file}")
        cell = tops[0]

    layer_num, datatype = tuple(layer)
    polys: list[Polygon] = []

    def _consume_points(points) -> None:
        pts = [(float(x), float(y)) for x, y in points]
        if len(pts) < 3:
            return
        poly = ShapelyPolygon(pts)
        polys.extend(_clean_polygon(poly))

    for polygon in cell.polygons:
        if polygon.layer != layer_num or polygon.datatype != datatype:
            continue
        _consume_points(polygon.points)

    # Paths on the same layer (common in some GDS exports)
    for path in getattr(cell, "paths", []):
        try:
            path_layer = path.layers[0] if hasattr(path, "layers") else path.layer
            path_dtype = path.datatypes[0] if hasattr(path, "datatypes") else path.datatype
        except Exception:
            continue
        if path_layer != layer_num or path_dtype != datatype:
            continue
        try:
            for poly in path.to_polygons():
                _consume_points(poly.points)
        except Exception:
            continue

    def sort_key(p: Polygon):
        c = p.centroid
        return (float(c.x), float(c.y), float(p.area))

    return sorted(polys, key=sort_key)


def validate_surface_map(
    surface_map: dict,
    n_polygons: int | None = None,
) -> dict[str, dict]:
    """
    Normalize and validate a SurfaceMap dict.

    Accepted forms per entry:

    - ``{"polygons": [0, 1], "attr": 3}``
    - ``{"polygons": 0, "attr": 3}``
    - ``[0, 1]`` (attr auto-assigned later by caller if missing)

    Returns a normalized ``{name: {"polygons": [int, ...], "attr": int|None}}``.
    """
    if not isinstance(surface_map, dict) or len(surface_map) == 0:
        raise ValueError("surface_map must be a non-empty dict of name → tagging entry")

    normalized: dict[str, dict] = {}
    used_polys: dict[int, str] = {}
    used_attrs: dict[int, str] = {}

    for name, entry in surface_map.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"SurfaceMap keys must be non-empty strings, got {name!r}")
        if name in ("substrate", "air", "far_field", "dielectric_gap"):
            raise ValueError(
                f"SurfaceMap name {name!r} is reserved for auto-tagged entities"
            )

        if isinstance(entry, (list, tuple, set)):
            poly_ids = list(entry)
            attr = None
        elif isinstance(entry, dict):
            if "polygons" not in entry:
                raise ValueError(
                    f"SurfaceMap[{name!r}] dict must include 'polygons'"
                )
            polys = entry["polygons"]
            if isinstance(polys, (int, np.integer)):
                poly_ids = [int(polys)]
            else:
                poly_ids = list(polys)
            attr = entry.get("attr", None)
            if attr != None:
                attr = int(attr)
        else:
            raise ValueError(
                f"SurfaceMap[{name!r}] must be a dict or list of polygon ids"
            )

        if len(poly_ids) == 0:
            raise ValueError(f"SurfaceMap[{name!r}] has empty polygons list")

        clean_ids = []
        for pid in poly_ids:
            pid = int(pid)
            if n_polygons != None and (pid < 0 or pid >= n_polygons):
                raise ValueError(
                    f"SurfaceMap[{name!r}] polygon id {pid} out of range "
                    f"[0, {n_polygons - 1}]"
                )
            if pid in used_polys:
                raise ValueError(
                    f"Polygon id {pid} is assigned to both "
                    f"{used_polys[pid]!r} and {name!r}"
                )
            used_polys[pid] = name
            clean_ids.append(pid)

        if attr != None:
            if attr <= 0:
                raise ValueError(
                    f"SurfaceMap[{name!r}] attr must be a positive integer"
                )
            if attr in used_attrs:
                raise ValueError(
                    f"Attribute id {attr} is assigned to both "
                    f"{used_attrs[attr]!r} and {name!r}"
                )
            used_attrs[attr] = name

        normalized[name] = {"polygons": clean_ids, "attr": attr}

    return normalized


def assign_missing_attrs(surface_map: dict[str, dict], start: int = 1) -> dict[str, dict]:
    """Fill missing ``attr`` values with the next free positive integers."""
    used = {v["attr"] for v in surface_map.values() if v["attr"] != None}
    next_attr = int(start)
    out = {}
    for name, entry in surface_map.items():
        attr = entry["attr"]
        if attr == None:
            while next_attr in used:
                next_attr += 1
            attr = next_attr
            used.add(attr)
            next_attr += 1
        out[name] = {"polygons": list(entry["polygons"]), "attr": int(attr)}
    return out


def inspect_gds(
    gds_file: str | Path,
    layer: tuple[int, int] = (1, 0),
    cell_name: str | None = None,
    *,
    labeling: bool = True,
    zoom_to_polygons: list[int] | int | None = None,
    crop: tuple | None = None,
    show: bool = True,
    save: str | Path | None = None,
) -> pd.DataFrame:
    """
    Plot GDS polygons with stable ids and return a summary DataFrame.

    Use the returned ``poly_id`` values when building a SurfaceMap for
    :func:`mesh_gds`.
    """
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    polys = load_gds_polygons(gds_file, layer=layer, cell_name=cell_name)
    if len(polys) == 0:
        raise ValueError(
            f"No polygons found on layer {tuple(layer)} in {gds_file}"
            + (f" (cell={cell_name!r})" if cell_name else "")
        )

    rows = []
    for i, p in enumerate(polys):
        minx, miny, maxx, maxy = p.bounds
        c = p.centroid
        rows.append(
            {
                "poly_id": i,
                "area": float(p.area),
                "centroid_x": float(c.x),
                "centroid_y": float(c.y),
                "xmin": float(minx),
                "ymin": float(miny),
                "xmax": float(maxx),
                "ymax": float(maxy),
                "n_exterior_points": int(len(p.exterior.coords) - 1),
            }
        )
    df = pd.DataFrame(rows)

    colors = (
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

    fig, ax = plt.subplots()
    # draw large → small so tiny polygons stay visible
    order = sorted(range(len(polys)), key=lambda i: polys[i].area, reverse=True)
    for i in order:
        p = polys[i]
        ring = np.asarray(p.exterior.coords)
        color = colors[i % len(colors)]
        ax.add_collection(
            PolyCollection(
                [ring[:, :2]],
                facecolors=color,
                edgecolors="k",
                linewidths=0.4,
                alpha=0.55,
            )
        )
        for interior in p.interiors:
            hole = np.asarray(interior.coords)
            ax.add_collection(
                PolyCollection(
                    [hole[:, :2]],
                    facecolors="white",
                    edgecolors="k",
                    linewidths=0.3,
                    alpha=1.0,
                )
            )

    full_xmin = float(df["xmin"].min())
    full_xmax = float(df["xmax"].max())
    full_ymin = float(df["ymin"].min())
    full_ymax = float(df["ymax"].max())

    if zoom_to_polygons != None and crop != None:
        raise ValueError("Use only one of zoom_to_polygons or crop.")

    if zoom_to_polygons != None:
        if isinstance(zoom_to_polygons, (int, np.integer)):
            zoom_ids = [int(zoom_to_polygons)]
        else:
            zoom_ids = [int(x) for x in zoom_to_polygons]
        for pid in zoom_ids:
            if pid < 0 or pid >= len(polys):
                raise ValueError(f"zoom_to_polygons id {pid} out of range")
        xs, ys = [], []
        for pid in zoom_ids:
            minx, miny, maxx, maxy = polys[pid].bounds
            xs.extend([minx, maxx])
            ys.extend([miny, maxy])
        pad = 0.05 * max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
        xmin, xmax = min(xs) - pad, max(xs) + pad
        ymin, ymax = min(ys) - pad, max(ys) + pad
    elif crop != None:
        center, span = crop
        cx, cy = center
        xmin, xmax = cx - span, cx + span
        ymin, ymax = cy - span, cy + span
    else:
        pad = 0.02 * max(full_xmax - full_xmin, full_ymax - full_ymin, 1e-9)
        xmin, xmax = full_xmin - pad, full_xmax + pad
        ymin, ymax = full_ymin - pad, full_ymax + pad

    if labeling:
        from shapely.geometry import Point as ShapelyPoint

        # Color-matched top-right callouts so nested/centered polygons stay
        # distinguishable (label color == surface color + arrow to attach point).
        xspan = max(xmax - xmin, 1e-12)
        yspan = max(ymax - ymin, 1e-12)
        dx = 0.035 * xspan
        dy = 0.035 * yspan
        occupied: list[tuple[float, float]] = []
        min_sep = 0.04 * max(xspan, yspan)

        # Draw large → small so small-polygon callouts stay on top.
        for i in sorted(range(len(polys)), key=lambda k: polys[k].area, reverse=True):
            p = polys[i]
            color = colors[i % len(colors)]
            minx_p, miny_p, maxx_p, maxy_p = p.bounds
            anchor_x, anchor_y = float(maxx_p), float(maxy_p)
            # If the bbox corner is outside the polygon, snap to nearest boundary.
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

            ax.annotate(
                f"p{i}",
                xy=(anchor_x, anchor_y),
                xytext=(text_x, text_y),
                fontsize=8,
                fontweight="bold",
                ha="left",
                va="bottom",
                color=color,
                clip_on=False,
                arrowprops=dict(
                    arrowstyle="->",
                    color=color,
                    lw=1.0,
                    shrinkA=2,
                    shrinkB=2,
                ),
                bbox=dict(
                    boxstyle="round,pad=0.18",
                    facecolor="white",
                    edgecolor=color,
                    linewidth=1.2,
                    alpha=0.92,
                ),
            )
            ax.plot(
                [anchor_x],
                [anchor_y],
                marker="o",
                markersize=3.5,
                color=color,
                markeredgecolor="k",
                markeredgewidth=0.4,
                zorder=5,
            )

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(f"GDS polygons — layer {tuple(layer)} ({len(polys)} polys)")

    if save != None:
        fig.savefig(str(save), dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)

    return df


def _chip_bbox(polys: list[Polygon], margin_x: float, margin_y: float) -> Polygon:
    union = unary_union(polys)
    minx, miny, maxx, maxy = union.bounds
    return Polygon(
        [
            (minx - margin_x, miny - margin_y),
            (maxx + margin_x, miny - margin_y),
            (maxx + margin_x, maxy + margin_y),
            (minx - margin_x, maxy + margin_y),
        ]
    )


def _scale_polygon(poly: Polygon, mesh_scale: float) -> Polygon:
    if mesh_scale == 1.0:
        return poly
    return shapely_scale(poly, xfact=mesh_scale, yfact=mesh_scale, origin=(0, 0))


def mesh_gds(
    gds_file: str | Path,
    surface_map: dict,
    output_mesh: str | Path = "mesh_from_gds.msh",
    *,
    metal_layer: tuple[int, int] = (1, 0),
    cell_name: str | None = None,
    substrate_thickness: float = 500.0,
    airbox_height: float = 500.0,
    margin: float = 500.0,
    margin_x: float | None = None,
    margin_y: float | None = None,
    volume_mesh_size: float = 250.0,
    surface_mesh_size: float = 20.0,
    custom_surface_mesh: dict[str, float] | None = None,
    refinement_radius: float = 150.0,
    mesh_scale: float = 1.0,
    farfield_attr: int | str = "auto",
    substrate_attr: int | str = "auto",
    air_attr: int | str = "auto",
    identify_arcs: bool = False,
    fuzzy_value: float | None = None,
) -> pd.DataFrame:
    """
    Mesh a GDS layout with MeshWell for Palace.

    Auto-tags ``substrate``, ``air``, ``far_field``, and ``dielectric_gap``
    (CPW voids / chip margin on the metal plane — not a Palace BC). Metal
    surfaces come only from ``surface_map`` (no auto ground plane).

    **Units are micrometers (µm)** by default: geometry kwargs and GDS
    coordinates are treated as µm with ``mesh_scale=1`` (Palace
    ``L0 = 1e-6``). If the GDS is in mm, pass ``mesh_scale=1000`` and keep
    the µm kwargs, or scale the kwargs to mm and use ``mesh_scale=1``.

    ``identify_arcs`` defaults to ``False`` (MeshWell's own default). Enabling
    it on filleted GDS paths often triggers OpenCASCADE wire failures.
    """
    cad_occ, ModelManager, PolyPrism = _require_meshwell()
    import gmsh

    from .meshing import Mesh

    polys = load_gds_polygons(gds_file, layer=metal_layer, cell_name=cell_name)
    if len(polys) == 0:
        raise ValueError(
            f"No polygons found on layer {tuple(metal_layer)} in {gds_file}"
        )

    smap = assign_missing_attrs(
        validate_surface_map(surface_map, n_polygons=len(polys))
    )

    if margin_x == None:
        margin_x = margin
    if margin_y == None:
        margin_y = margin
    if custom_surface_mesh == None:
        custom_surface_mesh = {}

    # Auto volume / far_field attrs after user surface attrs
    max_user = max(v["attr"] for v in smap.values())
    if substrate_attr == "auto":
        substrate_attr = max_user + 1
    else:
        substrate_attr = int(substrate_attr)
    if air_attr == "auto":
        air_attr = int(substrate_attr) + 1
    else:
        air_attr = int(air_attr)
    if farfield_attr == "auto":
        farfield_attr = int(air_attr) + 1
    else:
        farfield_attr = int(farfield_attr)

    reserved = {
        "substrate": substrate_attr,
        "air": air_attr,
        "far_field": farfield_attr,
    }
    for name, attr in smap.items():
        for rname, rattr in reserved.items():
            if attr["attr"] == rattr:
                raise ValueError(
                    f"SurfaceMap[{name!r}] attr={rattr} collides with auto-tagged {rname!r}"
                )

    # Geometry in mesh units (µm by default). Snap ~1 nm to kill micro-edges
    # that break OCC wires without collapsing real JJ-scale features.
    snap = max(1e-3, 1e-6 * float(mesh_scale))
    scaled_polys: list[Any] = []
    for p in polys:
        cleaned = _clean_polygon(_scale_polygon(p, mesh_scale), snap=snap)
        if not cleaned:
            raise ValueError(
                "A SurfaceMap polygon became empty after cleaning/scaling; "
                "check GDS units and mesh_scale."
            )
        scaled_polys.append(
            cleaned[0] if len(cleaned) == 1 else unary_union(cleaned)
        )

    chip_parts = _clean_polygon(
        _scale_polygon(_chip_bbox(polys, float(margin_x), float(margin_y)), mesh_scale),
        snap=snap,
    )
    if not chip_parts:
        raise ValueError("Failed to build chip bounding box polygon")
    chip = chip_parts[0]

    z_sub = -float(substrate_thickness) * mesh_scale
    z_air = float(airbox_height) * mesh_scale
    h_vol = float(volume_mesh_size) * mesh_scale
    h_surf = float(surface_mesh_size) * mesh_scale
    h_refine = float(refinement_radius) * mesh_scale

    # Guard against accidentally tiny sizes (e.g. old mm defaults like 0.02 on a
    # µm GDS) which request billions of elements and hang after CAD.
    _minx, _miny, _maxx, _maxy = chip.bounds
    chip_span = max(_maxx - _minx, _maxy - _miny, 1e-30)
    est_surf_elems = (chip_span / max(h_surf, 1e-30)) ** 2
    if est_surf_elems > 5.0e7:
        raise ValueError(
            "Mesh size is far too fine for this layout and would hang for a very "
            f"long time (chip span ≈ {chip_span:.4g} mesh units, "
            f"surface_mesh_size → {h_surf:.4g}, rough surface-element estimate "
            f"~{est_surf_elems:.1e}). "
            "mesh_gds defaults are in µm (mesh_scale=1, surface_mesh_size=20, "
            "volume_mesh_size=250). If the GDS is in mm, pass mesh_scale=1000."
        )

    # Build non-overlapping SurfaceMap geometries (small features win).
    name_geoms: dict[str, Any] = {}
    for name, entry in smap.items():
        selected = []
        for idx in entry["polygons"]:
            selected.extend(_flatten_polygons(scaled_polys[idx]))
        if not selected:
            raise ValueError(f"SurfaceMap[{name!r}] produced no geometry")
        geom = selected[0] if len(selected) == 1 else unary_union(selected)
        name_geoms[name] = geom

    all_union = unary_union(list(name_geoms.values()))
    for name, geom in list(name_geoms.items()):
        others = all_union.difference(geom) if all_union is not None else None
        name_geoms[name] = _drop_covered_holes(geom, others)

    ordered_names = sorted(
        name_geoms.keys(),
        key=lambda n: (float(name_geoms[n].area), smap[n]["attr"], n),
    )

    claimed = None
    kept_geoms: dict[str, Any] = {}
    for name in ordered_names:
        geom = name_geoms[name]
        if claimed is not None and not claimed.is_empty:
            geom = geom.difference(claimed)
        cleaned_parts: list[Polygon] = []
        for part in _flatten_polygons(geom):
            cleaned_parts.extend(_clean_polygon(part, snap=snap))
        if not cleaned_parts:
            print(
                "USER WARNING: SurfaceMap[{!r}] was empty after overlap cleanup; "
                "skipping.".format(name)
            )
            continue
        geom = cleaned_parts[0] if len(cleaned_parts) == 1 else MultiPolygon(cleaned_parts)
        kept_geoms[name] = geom
        claimed = geom if claimed is None else unary_union([claimed, geom])

    if not kept_geoms:
        raise ValueError("No SurfaceMap surfaces remained after overlap cleanup")

    if fuzzy_value == None:
        fuzzy_value = float(snap)

    output_path = Path(output_mesh)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        "meshing GDS: chip_span={:.4g}, h_vol={:.4g}, h_surf={:.4g}, "
        "mesh_scale={:g} (mesh units)".format(
            chip_span, h_vol, h_surf, float(mesh_scale)
        )
    )

    # ------------------------------------------------------------------
    # Hybrid CAD:
    #   1) MeshWell builds substrate/air volumes
    #   2) Gmsh imprints SurfaceMap polygons onto z=0 so metals AND
    #      dielectric gaps become conformal faces of the volume interface
    #      (MeshWell PolySurface coplanar fragment leaves large ground
    #      planes as dangling surfaces — that is what plot_mesh showed).
    # ------------------------------------------------------------------
    volume_entities = [
        PolyPrism(
            polygons=chip,
            buffers={z_sub: 0.0, 0.0: 0.0},
            physical_name="substrate",
            mesh_order=100.0,
            identify_arcs=identify_arcs,
            point_tolerance=snap,
        ),
        PolyPrism(
            polygons=chip,
            buffers={0.0: 0.0, z_air: 0.0},
            physical_name="air",
            mesh_order=100.0,
            identify_arcs=identify_arcs,
            point_tolerance=snap,
        ),
    ]

    mm = None
    try:
        occ_entities = cad_occ(
            volume_entities,
            n_threads=1,
            point_tolerance=snap,
            fuzzy_value=float(fuzzy_value),
            progress_bars=True,
        )
        mm = ModelManager(n_threads=1, point_tolerance=snap)
        mm.ensure_initialized(str(mm.filename))
        mm.load_occ_entities(occ_entities)

        # Imprint metals AND dielectric gaps onto z=0. Metals alone leave the
        # CPW gaps / chip-margin as holes in the volume interface (no face to
        # mesh). Gap polygons are imprinted too but left untagged for Palace.
        tool_surfs: list[tuple[int, int]] = []
        tool_names: list[str | None] = []
        for name, geom in kept_geoms.items():
            size = float(custom_surface_mesh.get(name, surface_mesh_size)) * mesh_scale
            for part in _flatten_polygons(geom):
                tag = _gmsh_add_polygon_surface_xy(gmsh, part, z=0.0, lc=size)
                tool_surfs.append((2, int(tag)))
                tool_names.append(name)

        all_metal = unary_union(list(kept_geoms.values()))
        gap_geom = chip.difference(all_metal) if all_metal is not None else chip
        gap_parts: list[Polygon] = []
        for part in _flatten_polygons(gap_geom):
            gap_parts.extend(_clean_polygon(part, snap=snap))
        for part in gap_parts:
            tag = _gmsh_add_polygon_surface_xy(gmsh, part, z=0.0, lc=h_surf)
            tool_surfs.append((2, int(tag)))
            tool_names.append(None)  # dielectric gap — no Palace metal attr

        if not tool_surfs:
            raise ValueError("No metal surfaces were created for imprinting")

        vols = gmsh.model.getEntities(3)
        _out, out_map = gmsh.model.occ.fragment(vols, tool_surfs)
        gmsh.model.occ.synchronize()

        name_to_faces: dict[str, list[int]] = {n: [] for n in kept_geoms}
        gap_faces: set[int] = set()
        n_vols = len(vols)
        for i, name in enumerate(tool_names):
            for dim, tag in out_map[n_vols + i]:
                if int(dim) != 2:
                    continue
                tag = int(tag)
                if name == None:
                    gap_faces.add(tag)
                else:
                    name_to_faces[name].append(tag)

        metal_faces = {f for faces in name_to_faces.values() for f in faces}
        z_tol = max(1e-6, 1e-9 * chip_span)

        def _assign_palace_groups() -> None:
            """(Re)write physical groups. Call again after meshing — Gmsh/MeshWell
            can resurrect interface names like ``substrate___air`` during generate.
            """
            existing = list(gmsh.model.getPhysicalGroups())
            if existing:
                gmsh.model.removePhysicalGroups(existing)

            sub_vols: list[int] = []
            air_vols: list[int] = []
            for dim, tag in gmsh.model.getEntities(3):
                _, _, zc = gmsh.model.occ.getCenterOfMass(dim, tag)
                (sub_vols if zc < 0 else air_vols).append(int(tag))
            if not sub_vols or not air_vols:
                raise RuntimeError(
                    "Failed to identify substrate/air volumes after metal imprint"
                )
            gmsh.model.addPhysicalGroup(3, sub_vols, int(substrate_attr))
            gmsh.model.setPhysicalName(3, int(substrate_attr), "substrate")
            gmsh.model.addPhysicalGroup(3, air_vols, int(air_attr))
            gmsh.model.setPhysicalName(3, int(air_attr), "air")

            for name, faces in name_to_faces.items():
                if not faces:
                    raise ValueError(
                        f"SurfaceMap[{name!r}] did not produce any imprinted z=0 "
                        "face; check polygon ids / mesh_scale."
                    )
                attr = int(smap[name]["attr"])
                gmsh.model.addPhysicalGroup(2, faces, attr)
                gmsh.model.setPhysicalName(2, attr, name)

            # far_field: outer box faces only (not metals, not dielectric gaps).
            vol_boundary = set()
            for dim, tag in gmsh.model.getEntities(3):
                for bd, bt in gmsh.model.getBoundary(
                    [(dim, tag)], combined=False, oriented=False, recursive=False
                ):
                    if bd == 2:
                        vol_boundary.add(int(bt))
            far_faces: list[int] = []
            for tag in sorted(vol_boundary):
                if tag in metal_faces or tag in gap_faces:
                    continue
                try:
                    _xmin, _ymin, zmin, _xmax, _ymax, zmax = gmsh.model.getBoundingBox(
                        2, tag
                    )
                except Exception:
                    continue
                # Skip any remaining z=0 interface scraps.
                if abs(zmin) <= z_tol and abs(zmax) <= z_tol:
                    continue
                far_faces.append(tag)
            if far_faces:
                gmsh.model.addPhysicalGroup(2, far_faces, int(farfield_attr))
                gmsh.model.setPhysicalName(2, int(farfield_attr), "far_field")

            # Keep gap faces in the .msh (SaveAll=0 drops untagged entities).
            # Not a Palace BC — leave out of Boundaries so gaps stay dielectric.
            if gap_faces:
                gap_attr = int(farfield_attr) + 1
                gmsh.model.addPhysicalGroup(2, sorted(gap_faces), gap_attr)
                gmsh.model.setPhysicalName(2, gap_attr, "dielectric_gap")

        _assign_palace_groups()

        # Mesh size: bulk + threshold refinement near metal boundaries.
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", min(h_surf, h_vol))
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", h_vol)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)

        mesh_fields: list[int] = []
        for name, faces in name_to_faces.items():
            size = float(custom_surface_mesh.get(name, surface_mesh_size)) * mesh_scale
            # Constant size on metal surfaces
            const_f = gmsh.model.mesh.field.add("Constant")
            gmsh.model.mesh.field.setNumber(const_f, "VIn", size)
            gmsh.model.mesh.field.setNumber(const_f, "VOut", h_vol)
            gmsh.model.mesh.field.setNumbers(const_f, "SurfacesList", faces)
            mesh_fields.append(const_f)

            if h_refine > 0 and size < h_vol:
                # Curves bounding these faces
                curves: list[int] = []
                for ftag in faces:
                    for cd, ct in gmsh.model.getBoundary(
                        [(2, ftag)], combined=False, oriented=False, recursive=False
                    ):
                        if cd == 1:
                            curves.append(int(ct))
                if curves:
                    dist_f = gmsh.model.mesh.field.add("Distance")
                    gmsh.model.mesh.field.setNumbers(dist_f, "CurvesList", curves)
                    gmsh.model.mesh.field.setNumber(dist_f, "Sampling", 100)
                    thr_f = gmsh.model.mesh.field.add("Threshold")
                    gmsh.model.mesh.field.setNumber(thr_f, "InField", dist_f)
                    gmsh.model.mesh.field.setNumber(thr_f, "SizeMin", size)
                    gmsh.model.mesh.field.setNumber(thr_f, "SizeMax", h_vol)
                    gmsh.model.mesh.field.setNumber(thr_f, "DistMin", 0.0)
                    gmsh.model.mesh.field.setNumber(thr_f, "DistMax", h_refine)
                    mesh_fields.append(thr_f)

        if len(mesh_fields) == 1:
            gmsh.model.mesh.field.setAsBackgroundMesh(mesh_fields[0])
        elif len(mesh_fields) > 1:
            min_f = gmsh.model.mesh.field.add("Min")
            gmsh.model.mesh.field.setNumbers(min_f, "FieldsList", mesh_fields)
            gmsh.model.mesh.field.setAsBackgroundMesh(min_f)

        gmsh.model.mesh.generate(3)
        # Meshing can restore MeshWell interface group names; rewrite Palace tags.
        _assign_palace_groups()
        gmsh.option.setNumber("Mesh.MshFileVersion", 4.1)
        gmsh.option.setNumber("Mesh.Binary", 0)
        gmsh.option.setNumber("Mesh.SaveAll", 0)
        gmsh.write(str(output_path))
    except Exception as e:
        msg = str(e)
        raise RuntimeError(
            "MeshWell/OpenCASCADE failed while building the GDS mesh "
            f"({type(e).__name__}: {msg}). "
            "Common causes: invalid/overlapping GDS polygons or mesh_scale "
            "mismatch. Check SurfaceMap polygons via inspect_gds(...)."
        ) from e
    finally:
        if mm != None:
            try:
                mm.finalize()
            except Exception:
                pass
        if gmsh.isInitialized():
            gmsh.finalize()

    # Gmsh MSH4 export can write volume $PhysicalNames tags as 1/2 even when
    # entity physical tags are the Palace ids (13/14/...). Patch the names block
    # so get_mesh_attributes / Palace config match the entity tags.
    _fix_volume_physical_names(
        output_path,
        substrate_attr=int(substrate_attr),
        air_attr=int(air_attr),
    )

    mesh_attributes = Mesh.get_mesh_attributes(str(output_path))
    return mesh_attributes.sort_values("ID")


def _fix_volume_physical_names(
    mesh_path: Path,
    substrate_attr: int,
    air_attr: int,
) -> None:
    """Align volume entries in ``$PhysicalNames`` with Palace attribute ids."""
    import re

    text = Path(mesh_path).read_text()
    begin = text.find("$PhysicalNames")
    end = text.find("$EndPhysicalNames")
    if begin < 0 or end < 0:
        return
    block = text[begin:end]
    block2 = re.sub(
        r'(?m)^3\s+\d+\s+"substrate"[ \t]*$',
        f'3 {int(substrate_attr)} "substrate"',
        block,
    )
    block2 = re.sub(
        r'(?m)^3\s+\d+\s+"air"[ \t]*$',
        f'3 {int(air_attr)} "air"',
        block2,
    )
    if block2 != block:
        Path(mesh_path).write_text(text[:begin] + block2 + text[end:])
