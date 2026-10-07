"""
GDS inspection and MeshWell-backed meshing for Palace workflows.

This module implements the GDS path:

1. :func:`inspect_gds` — plot metal ``p*`` or gap ``g*`` ids (``gaps_only``)
2. :func:`validate_surface_map` / SurfaceMap — name → polygon ids + attr
3. Optional :func:`validate_gap_map` / GapMap — name → gap ids + attr
4. :func:`mesh_gds` — MeshWell CAD/mesh with auto ``substrate``, ``air``,
   ``far_field``, plus SurfaceMap metals and optional named ``gap_map``
   surfaces (no catch-all gap tag)

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
        from meshwell.orchestrator import generate_mesh
        from meshwell.polyprism import PolyPrism
        from meshwell.polysurface import PolySurface
        from meshwell.resolution import ConstantInField, ThresholdField
    except ImportError as e:
        raise ImportError(
            "GDS meshing requires 'meshwell' and 'gdstk'. "
            "Reinstall pypalace (or: pip install meshwell gdstk)."
        ) from e
    return generate_mesh, PolyPrism, PolySurface, ConstantInField, ThresholdField


def _fill_holes(geom) -> Any:
    """Return exterior-only polygons (MeshWell mesh_order carves interior voids)."""
    parts: list[Polygon] = []
    for p in _flatten_polygons(geom):
        if p.is_empty or p.area <= 0:
            continue
        parts.append(Polygon(list(p.exterior.coords)))
    if not parts:
        return geom
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


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


def _drop_covered_holes(geom, others, cover_frac: float = 0.98) -> Any:
    """
    Drop holes that are already represented by other SurfaceMap metals.

    GDS ground planes often include cutouts that nearly match island polygons.
    Emitting both the hole wire and the island PolySurface creates coincident
    OpenCASCADE edges that frequently fail with ``Could not fix wire``.

    Only near-duplicate cutouts are removed (default ``cover_frac=0.98``).
    A lower threshold would also delete real CPW trenches that merely contain
    islands, which then get filled and tagged as ground.
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


def normalize_gds_layers(layers: Any) -> list[tuple[int, int]]:
    """
    Normalize GDS ``(layer, datatype)`` specs to a non-empty list of pairs.

    Accepts ``[(1, 0), (2, 0)]`` (preferred) or a single pair ``(1, 0)``.
    Duplicates are dropped (first wins). ``None`` is not valid here — pass
    ``layers=None`` into :func:`load_gds_polygons` / :func:`inspect_gds` /
    :func:`mesh_gds` to mean **all layers** in the cell.
    """
    if layers is None:
        raise ValueError(
            "layers=None means 'all layers' at the load/inspect/mesh API; "
            "normalize_gds_layers requires an explicit layer list"
        )

    def _as_pair(item: Any, *, label: str) -> tuple[int, int]:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(
                f"{label} must be (layer, datatype) pairs; got {item!r}"
            )
        try:
            return (int(item[0]), int(item[1]))
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"{label} entries must be integer (layer, datatype); got {item!r}"
            ) from e

    # Single pair: layers=(1, 0) → [(1, 0)]
    if (
        isinstance(layers, (tuple, list))
        and len(layers) == 2
        and not isinstance(layers[0], (tuple, list))
        and not isinstance(layers[1], (tuple, list))
    ):
        return [_as_pair(layers, label="layers")]

    if not isinstance(layers, (tuple, list)) or len(layers) == 0:
        raise ValueError(
            "layers must be a non-empty sequence of (layer, datatype) pairs, "
            "e.g. [(1, 0)] or [(1, 0), (2, 0)], or None for all layers"
        )

    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for item in layers:
        pair = _as_pair(item, label="layers")
        if pair in seen:
            continue
        seen.add(pair)
        out.append(pair)
    if not out:
        raise ValueError("layers must contain at least one (layer, datatype) pair")
    return out


def _open_gds_cell(gds_file: str | Path, cell_name: str | None = None):
    """Read a GDS and return the selected cell (top-level if ``cell_name`` omitted)."""
    import gdstk

    library = gdstk.read_gds(str(gds_file))
    if cell_name:
        cell = next((c for c in library.cells if c.name == cell_name), None)
        if cell is None:
            raise ValueError(f"Cell {cell_name!r} not found in {gds_file}")
        return cell
    tops = library.top_level()
    if not tops:
        raise ValueError(f"No top-level cell found in {gds_file}")
    return tops[0]


def discover_gds_layers(cell) -> list[tuple[int, int]]:
    """Return sorted unique ``(layer, datatype)`` pairs present on a gdstk cell."""
    pairs: set[tuple[int, int]] = set()
    for polygon in cell.polygons:
        pairs.add((int(polygon.layer), int(polygon.datatype)))
    for path in getattr(cell, "paths", []):
        try:
            path_layer = path.layers[0] if hasattr(path, "layers") else path.layer
            path_dtype = (
                path.datatypes[0] if hasattr(path, "datatypes") else path.datatype
            )
        except Exception:
            continue
        pairs.add((int(path_layer), int(path_dtype)))
    return sorted(pairs)


def resolve_gds_layers(
    gds_file: str | Path,
    layers: Any = None,
    cell_name: str | None = None,
) -> list[tuple[int, int]]:
    """
    Resolve ``layers`` for a GDS cell.

    ``None`` → every ``(layer, datatype)`` present on the cell (sorted).
    Otherwise → :func:`normalize_gds_layers`.
    """
    _require_meshwell()
    if layers is None:
        return discover_gds_layers(_open_gds_cell(gds_file, cell_name))
    return normalize_gds_layers(layers)


def load_gds_polygons(
    gds_file: str | Path,
    layers: Any = None,
    cell_name: str | None = None,
) -> list[Polygon]:
    """
    Load polygons from one or more GDS layers as a stable-ordered list.

    All selected layers are merged onto one plane (same z=0 metal plane in
    :func:`mesh_gds`). Polygons are kept separate (not unioned), so
    overlapping shapes such as a JJ on an island remain distinct for
    SurfaceMap tagging.

    Parameters
    ----------
    layers :
        Sequence of ``(layer, datatype)`` pairs, e.g. ``[(1, 0)]`` or
        ``[(1, 0), (2, 0)]``. ``None`` (default) loads **all** layers
        present in the cell. A single pair ``(1, 0)`` is also accepted.

    Order is by ``(centroid_x, centroid_y, area, layer, datatype)`` so ids
    stay stable across reloads for the same layer set.
    """
    from shapely.geometry import Polygon as ShapelyPolygon

    # Ensure meshwell/gdstk are importable early for a clear error message.
    _require_meshwell()

    cell = _open_gds_cell(gds_file, cell_name)
    layer_list = (
        discover_gds_layers(cell)
        if layers is None
        else normalize_gds_layers(layers)
    )
    wanted = set(layer_list)

    # (polygon, layer, datatype) — layer/datatype kept for stable sort ties.
    tagged: list[tuple[Polygon, int, int]] = []

    def _consume_points(points, layer_num: int, datatype: int) -> None:
        pts = [(float(x), float(y)) for x, y in points]
        if len(pts) < 3:
            return
        poly = ShapelyPolygon(pts)
        for cleaned in _clean_polygon(poly):
            tagged.append((cleaned, layer_num, datatype))

    for polygon in cell.polygons:
        pair = (int(polygon.layer), int(polygon.datatype))
        if pair not in wanted:
            continue
        _consume_points(polygon.points, pair[0], pair[1])

    # Paths on the same layers (common in some GDS exports)
    for path in getattr(cell, "paths", []):
        try:
            path_layer = path.layers[0] if hasattr(path, "layers") else path.layer
            path_dtype = path.datatypes[0] if hasattr(path, "datatypes") else path.datatype
        except Exception:
            continue
        pair = (int(path_layer), int(path_dtype))
        if pair not in wanted:
            continue
        try:
            for poly in path.to_polygons():
                _consume_points(poly.points, pair[0], pair[1])
        except Exception:
            continue

    def sort_key(item: tuple[Polygon, int, int]):
        p, layer_num, datatype = item
        c = p.centroid
        return (float(c.x), float(c.y), float(p.area), layer_num, datatype)

    tagged.sort(key=sort_key)
    return [p for p, _layer, _dtype in tagged]


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
        if name in ("substrate", "air", "air_below", "far_field", "dielectric_gap"):
            raise ValueError(
                f"SurfaceMap name {name!r} is reserved "
                "(substrate/air/far_field are auto-tagged; dielectric_gap is unused)"
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
        # Preserve polygons- or gaps-based maps.
        out_entry = {"attr": int(attr)}
        if "polygons" in entry:
            out_entry["polygons"] = list(entry["polygons"])
        if "gaps" in entry:
            out_entry["gaps"] = list(entry["gaps"])
        out[name] = out_entry
    return out


def _geom_sort_key(p: Polygon):
    c = p.centroid
    return (float(c.x), float(c.y), float(p.area))


def enumerate_gap_pieces(polys: list[Polygon]) -> list[Polygon]:
    """
    Stable-ordered interior dielectric-gap pieces: ``tight_bbox − metals``.

    Always uses the metal bounding box with **no** domain margin — chip-margin
    rings from ``mesh_gds(..., margin=...)`` are not nameable gaps. Ids match
    :func:`inspect_gds` (``gaps_only=True``) and :func:`mesh_gds` ``gap_map``.
    """
    if not polys:
        return []
    # Margin-free on purpose: gap_map is for interior voids (CPW trenches, etc.),
    # not the padded domain edge used for far_field / volume extent.
    chip = _chip_bbox(polys, 0.0, 0.0)
    metals = unary_union(polys)
    if metals is None or getattr(metals, "is_empty", False):
        raw = chip
    else:
        raw = chip.difference(metals)
    pieces = [p for p in _flatten_polygons(raw) if not p.is_empty and p.area > 0]
    return sorted(pieces, key=_geom_sort_key)


def validate_gap_map(
    gap_map: dict,
    n_gaps: int | None = None,
    *,
    reserved_names: set[str] | None = None,
) -> dict[str, dict]:
    """
    Normalize a GapMap dict: name → ``{"gaps": [gap_id, ...], "attr": int|None}``.

    Gap ids come from :func:`inspect_gds` with ``gaps_only=True`` /
    :func:`enumerate_gap_pieces` (interior / margin-free).
    """
    if not isinstance(gap_map, dict):
        raise ValueError("gap_map must be a dict of name → tagging entry")
    if len(gap_map) == 0:
        return {}

    reserved = set(reserved_names or ())
    reserved.update(
        {"substrate", "air", "air_below", "far_field", "dielectric_gap"}
    )
    normalized: dict[str, dict] = {}
    used_gaps: dict[int, str] = {}
    used_attrs: dict[int, str] = {}

    for name, entry in gap_map.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"GapMap keys must be non-empty strings, got {name!r}")
        if name in reserved:
            raise ValueError(f"GapMap name {name!r} is reserved")

        if isinstance(entry, (list, tuple, set)):
            gap_ids = list(entry)
            attr = None
        elif isinstance(entry, dict):
            if "gaps" not in entry:
                raise ValueError(f"GapMap[{name!r}] dict must include 'gaps'")
            gaps = entry["gaps"]
            if isinstance(gaps, (int, np.integer)):
                gap_ids = [int(gaps)]
            else:
                gap_ids = list(gaps)
            attr = entry.get("attr", None)
            if attr != None:
                attr = int(attr)
        else:
            raise ValueError(
                f"GapMap[{name!r}] must be a dict or list of gap ids"
            )

        if len(gap_ids) == 0:
            raise ValueError(f"GapMap[{name!r}] has empty gaps list")

        clean_ids = []
        for gid in gap_ids:
            gid = int(gid)
            if n_gaps != None and (gid < 0 or gid >= n_gaps):
                raise ValueError(
                    f"GapMap[{name!r}] gap id {gid} out of range "
                    f"[0, {n_gaps - 1}]"
                )
            if gid in used_gaps:
                raise ValueError(
                    f"Gap id {gid} is assigned to both "
                    f"{used_gaps[gid]!r} and {name!r}"
                )
            used_gaps[gid] = name
            clean_ids.append(gid)

        if attr != None:
            if attr <= 0:
                raise ValueError(
                    f"GapMap[{name!r}] attr must be a positive integer"
                )
            if attr in used_attrs:
                raise ValueError(
                    f"Attribute id {attr} is assigned to both "
                    f"{used_attrs[attr]!r} and {name!r}"
                )
            used_attrs[attr] = name

        normalized[name] = {"gaps": clean_ids, "attr": attr}

    return normalized


def inspect_gds(
    gds_file: str | Path,
    layers: Any = None,
    cell_name: str | None = None,
    *,
    labeling: bool = True,
    gaps_only: bool = False,
    zoom_to_polygons: list[int] | int | None = None,
    crop: tuple | None = None,
    show: bool = True,
    save: str | Path | None = None,
) -> pd.DataFrame:
    """
    Plot GDS polygons or dielectric-gap pieces with stable ids.

    Default (``gaps_only=False``): metal polygons labeled ``p*`` — use
    ``poly_id`` for a SurfaceMap.

    Gap mode (``gaps_only=True``): interior ``tight_bbox − metals`` pieces
    labeled ``g*`` — use ``gap_id`` for an optional ``gap_map`` in
    :func:`mesh_gds` (named gaps only; no catch-all leftover tag).
    Domain ``margin_*`` is not used here (and does not affect gap ids);
    padded chip-margin rings are not offered as nameable gaps.

    ``layers`` is a sequence of ``(layer, datatype)`` pairs merged onto one
    plane, or ``None`` (default) for **all** layers in the cell. Use the same
    value in :func:`mesh_gds`.
    """
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    layer_list = resolve_gds_layers(
        gds_file, layers=layers, cell_name=cell_name
    )
    polys = load_gds_polygons(
        gds_file, layers=layer_list, cell_name=cell_name
    )
    if layers is None:
        layer_label = "all"
    elif len(layer_list) == 1:
        layer_label = f"{layer_list[0]}"
    else:
        layer_label = "[" + ", ".join(str(p) for p in layer_list) + "]"
    if len(polys) == 0:
        raise ValueError(
            f"No polygons found on layers={layer_list} in {gds_file}"
            + (f" (cell={cell_name!r})" if cell_name else "")
        )

    if gaps_only:
        pieces = enumerate_gap_pieces(polys)
        if len(pieces) == 0:
            raise ValueError(
                "No interior dielectric-gap pieces found "
                "(tight metal bbox − metals is empty). Check layers."
            )
        id_key = "gap_id"
        label_prefix = "g"
        title = (
            f"GDS dielectric gaps — layers {layer_label} ({len(pieces)} gaps)"
        )
        draw_polys = pieces
        # Faint metal outlines for context only (no p* labels).
        outline_polys = polys
    else:
        id_key = "poly_id"
        label_prefix = "p"
        title = f"GDS polygons — layers {layer_label} ({len(polys)} polys)"
        draw_polys = polys
        outline_polys = []

    rows = []
    for i, p in enumerate(draw_polys):
        minx, miny, maxx, maxy = p.bounds
        c = p.centroid
        rows.append(
            {
                id_key: i,
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
    for op in outline_polys:
        ring = np.asarray(op.exterior.coords)
        ax.add_collection(
            PolyCollection(
                [ring[:, :2]],
                facecolors="none",
                edgecolors="0.55",
                linewidths=0.4,
                alpha=0.8,
            )
        )

    order = sorted(range(len(draw_polys)), key=lambda i: draw_polys[i].area, reverse=True)
    for i in order:
        p = draw_polys[i]
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
            if pid < 0 or pid >= len(draw_polys):
                raise ValueError(f"zoom_to_polygons id {pid} out of range")
        xs, ys = [], []
        for pid in zoom_ids:
            minx, miny, maxx, maxy = draw_polys[pid].bounds
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

        xspan = max(xmax - xmin, 1e-12)
        yspan = max(ymax - ymin, 1e-12)
        dx = 0.035 * xspan
        dy = 0.035 * yspan
        occupied: list[tuple[float, float]] = []
        min_sep = 0.04 * max(xspan, yspan)

        for i in sorted(
            range(len(draw_polys)), key=lambda k: draw_polys[k].area, reverse=True
        ):
            p = draw_polys[i]
            color = colors[i % len(colors)]
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

            ax.annotate(
                f"{label_prefix}{i}",
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
    ax.set_title(title)

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
    layers: Any = None,
    cell_name: str | None = None,
    substrate_thickness: float = 500.0,
    airbox_height: float = 500.0,
    airbox_height_below: float = 0.0,
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
    gap_map: dict | None = None,
    identify_arcs: bool = False,
    fuzzy_value: float | None = None,
) -> pd.DataFrame:
    """
    Mesh a GDS layout with MeshWell for Palace.

    Auto-tags ``substrate``, ``air``, and ``far_field``. Metal surfaces come
    only from ``surface_map`` (no auto ground plane). Optional ``gap_map``
    entries become named z=0 surfaces (tag + mesh size); anything not in
    ``gap_map`` stays the plain substrate/air interface (no catch-all gap
    physical group).

    **Units are micrometers (µm)** by default: geometry kwargs and GDS
    coordinates are treated as µm with ``mesh_scale=1`` (Palace
    ``L0 = 1e-6``). If the GDS is in mm, pass ``mesh_scale=1000`` and keep
    the µm kwargs, or scale the kwargs to mm and use ``mesh_scale=1``.

    CAD is pure MeshWell: SurfaceMap metals (CPW holes kept) and optional
    named gap pieces are ``PolySurface`` entities nested by ``mesh_order``;
    substrate/air are ``PolyPrism`` volumes. Shared z=0 faces are then
    classified against those footprints so large ground planes and named
    trenches land on the volume interface.

    ``layers`` selects GDS ``(layer, datatype)`` pairs merged onto the single
    z=0 metal plane. Default ``None`` = **all** layers in the cell. Pass the
    same value to :func:`inspect_gds` so ``poly_id`` / ``gap_id`` match.

    ``airbox_height`` is the vacuum above the metal plane (default 500 µm).
    ``airbox_height_below`` adds optional vacuum under the substrate
    (default **0** — same stack as before). When set, that volume shares the
    Palace ``air`` attribute and far_field grows to the new bottom / sides.

    Optional ``gap_map`` names **interior** gap pieces (ids from
    :func:`inspect_gds` with ``gaps_only=True``) for Palace post-processing
    and per-name ``custom_surface_mesh`` sizing (same dict / knobs as metals).
    Gap ids ignore ``margin_*`` (tight metal bbox only). Omitted / empty
    → metals only; unmapped trenches stay untagged volume interface.

    ``identify_arcs`` defaults to ``False`` (MeshWell's own default). Enabling
    it on filleted GDS paths often triggers OpenCASCADE wire failures.
    """
    (
        generate_mesh,
        PolyPrism,
        PolySurface,
        ConstantInField,
        ThresholdField,
    ) = _require_meshwell()

    from .meshing import Mesh

    layer_list = resolve_gds_layers(
        gds_file, layers=layers, cell_name=cell_name
    )
    polys = load_gds_polygons(
        gds_file, layers=layer_list, cell_name=cell_name
    )
    if len(polys) == 0:
        raise ValueError(
            f"No polygons found on layers={layer_list} in {gds_file}"
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
    if gap_map == None:
        gap_map = {}
    if float(substrate_thickness) <= 0:
        raise ValueError("substrate_thickness must be > 0")
    if float(airbox_height) <= 0:
        raise ValueError("airbox_height must be > 0")
    if float(airbox_height_below) < 0:
        raise ValueError("airbox_height_below must be >= 0 (0 keeps prior behavior)")

    # Interior gap pieces only (margin-free; same enum as inspect gaps_only).
    gap_pieces = enumerate_gap_pieces(polys)
    gmap = validate_gap_map(
        gap_map,
        n_gaps=len(gap_pieces),
        reserved_names=set(smap.keys()),
    )

    # Auto volume / far_field attrs after user surface attrs.
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
    for name, entry in smap.items():
        for rname, rattr in reserved.items():
            if entry["attr"] == rattr:
                raise ValueError(
                    f"SurfaceMap[{name!r}] attr={rattr} collides with auto-tagged {rname!r}"
                )

    # Named gap attrs: keep explicit ones, auto-fill after far_field.
    used_attrs = {int(v["attr"]) for v in smap.values()} | set(reserved.values())
    for name, entry in gmap.items():
        attr = entry["attr"]
        if attr != None:
            if int(attr) in used_attrs:
                raise ValueError(
                    f"GapMap[{name!r}] attr={attr} collides with an existing attribute"
                )
            used_attrs.add(int(attr))
    gmap = assign_missing_attrs(gmap, start=int(farfield_attr) + 1)
    for name, entry in gmap.items():
        if int(entry["attr"]) in reserved.values():
            raise ValueError(
                f"GapMap[{name!r}] attr={entry['attr']} collides with a reserved attribute"
            )
        if int(entry["attr"]) in {int(v["attr"]) for v in smap.values()}:
            raise ValueError(
                f"GapMap[{name!r}] attr={entry['attr']} collides with a SurfaceMap attribute"
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
    z_air_below = z_sub - float(airbox_height_below) * mesh_scale
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

    # Keep CPW holes in ground planes; only drop holes already covered by
    # other SurfaceMap metals. Named gap_map PolySurfaces (if any) sit above
    # metals in mesh_order. Palace tags are assigned afterward by classifying
    # shared z=0 faces against metal / named-gap footprints.
    name_geoms: dict[str, Any] = {}
    for name, entry in smap.items():
        selected = []
        for idx in entry["polygons"]:
            selected.extend(_flatten_polygons(scaled_polys[idx]))
        if not selected:
            raise ValueError(f"SurfaceMap[{name!r}] produced no geometry")
        geom = selected[0] if len(selected) == 1 else unary_union(selected)
        cleaned_parts: list[Polygon] = []
        for part in _flatten_polygons(geom):
            cleaned_parts.extend(_clean_polygon(part, snap=snap))
        if not cleaned_parts:
            raise ValueError(f"SurfaceMap[{name!r}] became empty after cleaning")
        name_geoms[name] = (
            cleaned_parts[0]
            if len(cleaned_parts) == 1
            else MultiPolygon(cleaned_parts)
        )

    all_union = unary_union(list(name_geoms.values()))
    for name, geom in list(name_geoms.items()):
        others = all_union.difference(geom) if all_union is not None else None
        cleaned_parts = []
        for part in _flatten_polygons(_drop_covered_holes(geom, others)):
            cleaned_parts.extend(_clean_polygon(part, snap=snap))
        if not cleaned_parts:
            raise ValueError(
                f"SurfaceMap[{name!r}] became empty after hole cleanup"
            )
        name_geoms[name] = (
            cleaned_parts[0]
            if len(cleaned_parts) == 1
            else MultiPolygon(cleaned_parts)
        )

    ordered_names = sorted(
        name_geoms.keys(),
        key=lambda n: (float(name_geoms[n].area), smap[n]["attr"], n),
    )
    if not ordered_names:
        raise ValueError("No SurfaceMap surfaces to mesh")
    if fuzzy_value == None:
        fuzzy_value = float(snap)

    output_path = Path(output_mesh)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        "meshing GDS (MeshWell): chip_span={:.4g}, h_vol={:.4g}, h_surf={:.4g}, "
        "mesh_scale={:g} (mesh units)".format(
            chip_span, h_vol, h_surf, float(mesh_scale)
        )
    )

    # Build named gap footprints before CAD (same ids as inspect gaps_only).
    gap_geoms: dict[str, Any] = {}
    for name, entry in gmap.items():
        parts: list[Polygon] = []
        for gid in entry["gaps"]:
            scaled_parts = _clean_polygon(
                _scale_polygon(gap_pieces[int(gid)], mesh_scale), snap=snap
            )
            parts.extend(scaled_parts)
        if not parts:
            raise ValueError(f"GapMap[{name!r}] became empty after scaling/cleaning")
        gap_geoms[name] = parts[0] if len(parts) == 1 else unary_union(parts)

    ordered_gap_names = sorted(
        gap_geoms.keys(),
        key=lambda n: (float(gap_geoms[n].area), gmap[n]["attr"], n),
    )

    entities: list[Any] = []
    for i, name in enumerate(ordered_names):
        entities.append(
            PolySurface(
                polygons=name_geoms[name],
                physical_name=name,
                mesh_order=float(i + 1),
                identify_arcs=identify_arcs,
                point_tolerance=snap,
            )
        )
    # Named gaps after metals so metal nesting wins on any overlap.
    n_metal = len(ordered_names)
    for i, name in enumerate(ordered_gap_names):
        entities.append(
            PolySurface(
                polygons=gap_geoms[name],
                physical_name=name,
                mesh_order=float(n_metal + i + 1),
                identify_arcs=identify_arcs,
                point_tolerance=snap,
            )
        )
    entities.append(
        PolyPrism(
            polygons=chip,
            buffers={z_sub: 0.0, 0.0: 0.0},
            physical_name="substrate",
            mesh_order=100.0,
            identify_arcs=identify_arcs,
            point_tolerance=snap,
        )
    )
    entities.append(
        PolyPrism(
            polygons=chip,
            buffers={0.0: 0.0, z_air: 0.0},
            physical_name="air",
            mesh_order=100.0,
            identify_arcs=identify_arcs,
            point_tolerance=snap,
        )
    )
    # Optional vacuum under the substrate (same Palace "air" attr after remap).
    # Default airbox_height_below=0 skips this so existing stacks are unchanged.
    if float(airbox_height_below) > 0:
        entities.append(
            PolyPrism(
                polygons=chip,
                buffers={z_air_below: 0.0, z_sub: 0.0},
                physical_name="air_below",
                mesh_order=100.0,
                identify_arcs=identify_arcs,
                point_tolerance=snap,
            )
        )

    # Same sizing path for SurfaceMap metals and named gap_map surfaces.
    resolution_specs: dict[str, list] = {}
    for name in list(ordered_names) + list(ordered_gap_names):
        size = float(custom_surface_mesh.get(name, surface_mesh_size)) * mesh_scale
        specs = [ConstantInField(apply_to="surfaces", resolution=size)]
        if h_refine > 0 and size < h_vol:
            specs.append(
                ThresholdField(
                    apply_to="curves",
                    sizemin=size,
                    sizemax=h_vol,
                    distmin=0.0,
                    distmax=h_refine,
                )
            )
        resolution_specs[name] = specs

    try:
        generate_mesh(
            entities,
            dim=3,
            output_mesh=output_path,
            default_characteristic_length=h_vol,
            point_tolerance=snap,
            fuzzy_value=float(fuzzy_value),
            progress_bars=True,
            n_threads=1,
            resolution_specs=resolution_specs,
            # Intermediate MSH 4.1 keeps OCC entity adjacency so remap can
            # call getBoundary; final write below is MSH 2.2 for Palace/MFEM.
            gmsh_version=4.1,
        )
    except Exception as e:
        msg = str(e)
        raise RuntimeError(
            "MeshWell/OpenCASCADE failed while building the GDS mesh "
            f"({type(e).__name__}: {msg}). "
            "Common causes: invalid/overlapping GDS polygons or mesh_scale "
            "mismatch. Check SurfaceMap polygons via inspect_gds(...)."
        ) from e

    _remap_palace_physical_groups(
        output_path,
        surface_attrs={n: int(smap[n]["attr"]) for n in ordered_names},
        surface_geoms=name_geoms,
        substrate_attr=int(substrate_attr),
        air_attr=int(air_attr),
        farfield_attr=int(farfield_attr),
        chip_span=chip_span,
        gap_attrs={n: int(gmap[n]["attr"]) for n in ordered_gap_names} if ordered_gap_names else None,
        gap_geoms=gap_geoms if gap_geoms else None,
    )

    mesh_attributes = Mesh.get_mesh_attributes(str(output_path))
    return mesh_attributes.sort_values("ID")


def _classify_z0_face(
    gmsh,
    face_tag: int,
    ordered_names: list[str],
    surface_geoms: dict[str, Any],
) -> str | None:
    """Vote a shared z=0 face into a named footprint, or ``None`` if untagged."""
    from shapely.geometry import Point

    if not ordered_names:
        return None

    try:
        _tags, coords, _p = gmsh.model.mesh.getNodes(
            2, int(face_tag), includeBoundary=True
        )
    except Exception:
        return None
    if coords is None or len(coords) < 3:
        return None
    pts = np.asarray(coords, dtype=float).reshape(-1, 3)[:, :2]
    if len(pts) > 250:
        pts = pts[:: max(1, len(pts) // 250)]

    votes = {name: 0 for name in ordered_names}
    miss_votes = 0
    for x, y in pts:
        p = Point(float(x), float(y))
        hit = None
        for name in ordered_names:  # small features first
            geom = surface_geoms[name]
            if geom.covers(p) or geom.contains(p):
                hit = name
                break
        if hit == None:
            miss_votes += 1
        else:
            votes[hit] += 1

    best_name = max(ordered_names, key=lambda n: votes[n])
    if votes[best_name] > miss_votes and votes[best_name] > 0:
        return best_name
    return None


def _remap_palace_physical_groups(
    mesh_path: Path,
    surface_attrs: dict[str, int],
    surface_geoms: dict[str, Any],
    substrate_attr: int,
    air_attr: int,
    farfield_attr: int,
    chip_span: float,
    gap_attrs: dict[str, int] | None = None,
    gap_geoms: dict[str, Any] | None = None,
) -> None:
    """Tag shared z=0 faces by SurfaceMap / optional GapMap footprints.

    Unmapped z=0 interface faces stay untagged (no catch-all gap group).
    """
    import gmsh

    z_tol = max(1e-6, 1e-9 * float(chip_span))
    ordered_names = sorted(
        surface_attrs.keys(),
        key=lambda n: (float(surface_geoms[n].area), surface_attrs[n], n),
    )
    gap_attrs = gap_attrs or {}
    gap_geoms = gap_geoms or {}
    ordered_gap_names = sorted(
        gap_attrs.keys(),
        key=lambda n: (float(gap_geoms[n].area), gap_attrs[n], n),
    )
    gmsh.initialize()
    try:
        gmsh.open(str(mesh_path))
        by_name: dict[str, tuple[int, list[int]]] = {}
        for dim, tag in gmsh.model.getPhysicalGroups():
            name = gmsh.model.getPhysicalName(dim, tag)
            ents = [int(x) for x in gmsh.model.getEntitiesForPhysicalGroup(dim, tag)]
            if name in by_name:
                prev_dim, prev_ents = by_name[name]
                if int(prev_dim) != int(dim):
                    raise RuntimeError(
                        f"Physical name {name!r} appears on multiple dimensions"
                    )
                by_name[name] = (int(dim), prev_ents + ents)
            else:
                by_name[name] = (int(dim), ents)

        if "substrate" not in by_name or "air" not in by_name:
            raise RuntimeError(
                "MeshWell mesh is missing substrate/air volume groups"
            )

        sub_vols = by_name["substrate"][1]
        # Optional under-substrate vacuum is meshed as air_below, then folded
        # into the Palace "air" attribute (same material).
        air_vols = list(by_name["air"][1])
        if "air_below" in by_name and by_name["air_below"][0] == 3:
            air_vols.extend(by_name["air_below"][1])

        def _boundary_faces(vols: list[int]) -> set[int]:
            faces: set[int] = set()
            for v in vols:
                for dim, tag in gmsh.model.getBoundary(
                    [(3, int(v))], combined=False, oriented=False, recursive=False
                ):
                    if int(dim) == 2:
                        faces.add(int(tag))
            return faces

        # Metal / gap tagging only on the metal plane (z=0). The substrate /
        # air_below interface at z=-t_sub is intentionally left untagged.
        shared = _boundary_faces(sub_vols) & _boundary_faces(air_vols)
        z0_shared: list[int] = []
        for tag in shared:
            try:
                _xmin, _ymin, zmin, _xmax, _ymax, zmax = gmsh.model.getBoundingBox(
                    2, tag
                )
            except Exception:
                continue
            if abs(zmin) <= z_tol and abs(zmax) <= z_tol:
                z0_shared.append(tag)

        # MeshWell name(s) for each face before we rewrite groups.
        face_mw_names: dict[int, list[str]] = {}
        for name, (dim, ents) in by_name.items():
            if dim != 2:
                continue
            for tag in ents:
                face_mw_names.setdefault(int(tag), []).append(name)

        name_to_faces: dict[str, list[int]] = {n: [] for n in ordered_names}
        named_gap_faces: dict[str, list[int]] = {n: [] for n in ordered_gap_names}
        for tag in z0_shared:
            mw_metal = [
                n for n in face_mw_names.get(tag, []) if n in surface_attrs
            ]
            mw_gap = [
                n for n in face_mw_names.get(tag, []) if n in gap_attrs
            ]
            if len(mw_metal) == 1:
                # Trust MeshWell when a SurfaceMap metal already owns the
                # shared face (tiny JJs etc.).
                label = mw_metal[0]
            elif len(mw_gap) == 1 and not mw_metal:
                # Trust MeshWell for named gap PolySurfaces.
                label = mw_gap[0]
            else:
                # Large ground often dangles as substrate___air — classify
                # by metal footprint, then optional named-gap footprint.
                label = _classify_z0_face(
                    gmsh, tag, ordered_names, surface_geoms
                )
                if label == None and ordered_gap_names:
                    label = _classify_z0_face(
                        gmsh, tag, ordered_gap_names, gap_geoms
                    )
            if label == None:
                continue  # untagged volume interface
            if label in named_gap_faces:
                named_gap_faces[label].append(tag)
            elif label in name_to_faces:
                name_to_faces[label].append(tag)

        for name in ordered_names:
            if not name_to_faces[name]:
                raise ValueError(
                    f"SurfaceMap[{name!r}] has no shared z=0 interface face after "
                    "classification; check polygon ids / mesh_scale."
                )
        for name in ordered_gap_names:
            if not named_gap_faces[name]:
                raise ValueError(
                    f"GapMap[{name!r}] has no shared z=0 gap face after "
                    "classification; check gap ids vs inspect_gds(gaps_only=True)."
                )
        existing = list(gmsh.model.getPhysicalGroups())
        if existing:
            gmsh.model.removePhysicalGroups(existing)

        def _add(dim: int, ents: list[int], attr: int, name: str) -> None:
            if not ents:
                return
            gmsh.model.addPhysicalGroup(dim, sorted(set(ents)), int(attr))
            gmsh.model.setPhysicalName(dim, int(attr), name)

        _add(3, sub_vols, substrate_attr, "substrate")
        _add(3, air_vols, air_attr, "air")
        metal_faces: set[int] = set()
        for name, attr in surface_attrs.items():
            faces = name_to_faces[name]
            metal_faces.update(faces)
            _add(2, faces, attr, name)
        tagged_gap_faces: set[int] = set()
        for name, attr in gap_attrs.items():
            faces = named_gap_faces[name]
            tagged_gap_faces.update(faces)
            _add(2, faces, attr, name)

        # Exterior box faces from MeshWell boundary groups (…___None).
        # z=0 interface faces (metals, named gaps, untagged trenches) are
        # skipped via the z≈0 bbox filter below.
        far_faces: list[int] = []
        for name, (dim, ents) in by_name.items():
            if dim != 2 or not name.endswith("___None"):
                continue
            for tag in ents:
                if tag in metal_faces or tag in tagged_gap_faces:
                    continue
                try:
                    _xmin, _ymin, zmin, _xmax, _ymax, zmax = gmsh.model.getBoundingBox(
                        2, tag
                    )
                except Exception:
                    continue
                if abs(zmin) <= z_tol and abs(zmax) <= z_tol:
                    continue
                far_faces.append(tag)
        _add(2, far_faces, farfield_attr, "far_field")

        # Final Palace/MFEM-facing file must be MSH 2.2. Intermediate MeshWell
        # output stays 4.1 so entity adjacency survives gmsh.open for remap.
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.option.setNumber("Mesh.Binary", 0)
        gmsh.option.setNumber("Mesh.SaveAll", 0)
        gmsh.write(str(mesh_path))
    finally:
        if gmsh.isInitialized():
            gmsh.finalize()
