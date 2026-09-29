"""
GDS inspection and MeshWell-backed meshing for Palace workflows.

This module implements the GDS path:

1. :func:`inspect_gds` — plot polygons with stable ids and return a DataFrame
2. :func:`validate_surface_map` / SurfaceMap dict — name → polygon ids + attr
3. :func:`mesh_gds` — MeshWell CAD/mesh with auto ``substrate``, ``air``,
   ``far_field`` tags (no auto ground plane)

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

    # Touch meshwell optional import early for a clear error message.
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
    for polygon in cell.polygons:
        if polygon.layer != layer_num or polygon.datatype != datatype:
            continue
        points = [(float(x), float(y)) for x, y in polygon.points]
        if len(points) < 3:
            continue
        poly = ShapelyPolygon(points)
        if not poly.is_valid:
            poly = poly.buffer(0)
        polys.extend(_flatten_polygons(poly))

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
        if name in ("substrate", "air", "far_field"):
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

    if labeling:
        for i, p in enumerate(polys):
            c = p.centroid
            ax.annotate(
                f"p{i}",
                (c.x, c.y),
                fontsize=8,
                ha="center",
                va="center",
                color="black",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7),
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
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)
    elif crop != None:
        center, span = crop
        cx, cy = center
        ax.set_xlim(cx - span, cx + span)
        ax.set_ylim(cy - span, cy + span)
    else:
        pad = 0.02 * max(full_xmax - full_xmin, full_ymax - full_ymin, 1e-9)
        ax.set_xlim(full_xmin - pad, full_xmax + pad)
        ax.set_ylim(full_ymin - pad, full_ymax + pad)

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


def _remap_palace_physical_groups(
    mesh_path: Path,
    surface_name_to_attr: dict[str, int],
    substrate_attr: int,
    air_attr: int,
    farfield_attr: int,
) -> None:
    """Rewrite physical groups to Palace attr ids / names."""
    import gmsh

    gmsh.initialize()
    try:
        gmsh.open(str(mesh_path))

        # Collect elementary entities by current physical name
        name_to_ents: dict[tuple[int, str], list[int]] = {}
        for dim, tag in gmsh.model.getPhysicalGroups():
            name = gmsh.model.getPhysicalName(dim, tag)
            ents = [int(e) for e in gmsh.model.getEntitiesForPhysicalGroup(dim, tag)]
            name_to_ents[(dim, name)] = ents

        # Must pass the group list explicitly (bare removePhysicalGroups is a no-op here).
        existing = list(gmsh.model.getPhysicalGroups())
        if existing:
            gmsh.model.removePhysicalGroups(existing)

        # Volumes
        for dim, name, attr in (
            (3, "substrate", substrate_attr),
            (3, "air", air_attr),
        ):
            ents = name_to_ents.get((dim, name), [])
            if ents:
                gmsh.model.addPhysicalGroup(dim, ents, tag=int(attr))
                gmsh.model.setPhysicalName(dim, int(attr), name)

        # User metal surfaces
        for name, attr in surface_name_to_attr.items():
            ents = name_to_ents.get((2, name), [])
            if not ents:
                raise ValueError(
                    f"Expected meshed surface physical group {name!r} was not found"
                )
            gmsh.model.addPhysicalGroup(2, ents, tag=int(attr))
            gmsh.model.setPhysicalName(2, int(attr), name)

        # far_field = exterior boundaries of substrate and air
        far_ents = []
        for (dim, name), ents in name_to_ents.items():
            if dim == 2 and name.endswith("___None"):
                far_ents.extend(ents)
        seen = set()
        uniq = []
        for e in far_ents:
            if e not in seen:
                seen.add(e)
                uniq.append(e)
        if uniq:
            gmsh.model.addPhysicalGroup(2, uniq, tag=int(farfield_attr))
            gmsh.model.setPhysicalName(2, int(farfield_attr), "far_field")

        gmsh.write(str(mesh_path))
    finally:
        if gmsh.isInitialized():
            gmsh.finalize()


def mesh_gds(
    gds_file: str | Path,
    surface_map: dict,
    output_mesh: str | Path = "mesh_from_gds.msh",
    *,
    metal_layer: tuple[int, int] = (1, 0),
    cell_name: str | None = None,
    substrate_thickness: float = 0.5,
    airbox_height: float = 0.5,
    margin: float = 0.5,
    margin_x: float | None = None,
    margin_y: float | None = None,
    volume_mesh_size: float = 0.25,
    surface_mesh_size: float = 0.02,
    custom_surface_mesh: dict[str, float] | None = None,
    refinement_radius: float = 0.15,
    mesh_scale: float = 1000.0,
    farfield_attr: int | str = "auto",
    substrate_attr: int | str = "auto",
    air_attr: int | str = "auto",
    identify_arcs: bool = True,
) -> pd.DataFrame:
    """
    Mesh a GDS layout with MeshWell for Palace.

    Auto-tags ``substrate``, ``air``, and ``far_field``. Metal surfaces come
    only from ``surface_map`` (no auto ground plane).

    Parameters mirror :meth:`pypalace.meshing.Mesh.mesh_Quantum_Metal_design`
    where applicable. Coordinates are multiplied by ``mesh_scale`` before
    meshing (default ``1000`` for mm design units → µm mesh units with
    Palace ``L0 = 1e-6``).
    """
    (
        generate_mesh,
        PolyPrism,
        PolySurface,
        ConstantInField,
        ThresholdField,
    ) = _require_meshwell()

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

    # Geometry in mesh units
    scaled_polys = [_scale_polygon(p, mesh_scale) for p in polys]
    chip = _scale_polygon(
        _chip_bbox(polys, float(margin_x), float(margin_y)), mesh_scale
    )
    z_sub = -float(substrate_thickness) * mesh_scale
    z_air = float(airbox_height) * mesh_scale
    h_vol = float(volume_mesh_size) * mesh_scale
    h_surf = float(surface_mesh_size) * mesh_scale
    h_refine = float(refinement_radius) * mesh_scale

    entities: list[Any] = []
    resolution_specs: dict[str, list] = {}

    # Metal surfaces: lower mesh_order wins overlaps; tag JJ-like small attrs first
    ordered_names = sorted(smap.keys(), key=lambda n: (smap[n]["attr"], n))
    for order, name in enumerate(ordered_names):
        entry = smap[name]
        selected = [scaled_polys[i] for i in entry["polygons"]]
        if len(selected) == 1:
            geom = selected[0]
        else:
            geom = MultiPolygon(selected)
        entities.append(
            PolySurface(
                polygons=geom,
                physical_name=name,
                mesh_order=float(order),
                identify_arcs=identify_arcs,
            )
        )
        size = float(custom_surface_mesh.get(name, surface_mesh_size)) * mesh_scale
        specs = [ConstantInField(resolution=size, apply_to="surfaces")]
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

    # Volumes (higher mesh_order so surfaces win the metal plane)
    entities.append(
        PolyPrism(
            polygons=chip,
            buffers={z_sub: 0.0, 0.0: 0.0},
            physical_name="substrate",
            mesh_order=100.0,
            identify_arcs=identify_arcs,
        )
    )
    entities.append(
        PolyPrism(
            polygons=chip,
            buffers={0.0: 0.0, z_air: 0.0},
            physical_name="air",
            mesh_order=100.0,
            identify_arcs=identify_arcs,
        )
    )

    output_path = Path(output_mesh)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_mesh(
        entities=entities,
        dim=3,
        output_mesh=str(output_path),
        default_characteristic_length=h_vol,
        resolution_specs=resolution_specs,
        n_threads=1,
    )

    _remap_palace_physical_groups(
        output_path,
        {name: entry["attr"] for name, entry in smap.items()},
        substrate_attr=int(substrate_attr),
        air_attr=int(air_attr),
        farfield_attr=int(farfield_attr),
    )

    # Local import to avoid circular import at module load
    from .meshing import Mesh

    mesh_attributes = Mesh.get_mesh_attributes(str(output_path))
    return mesh_attributes.sort_values("ID")
