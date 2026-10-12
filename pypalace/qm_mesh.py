"""
Quantum Metal → MeshWell adapter for Palace.

Builds a SurfaceMap (auto metal tags + QM-only auto ``ground_plane``) from
a Qiskit Metal design and meshes via :func:`pypalace.gds_mesh.mesh_polygons`.

Airbridges are not supported yet — detection raises ``NotImplementedError``.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .gds_mesh import (
    _chip_bbox,
    _flatten_polygons,
    assign_missing_attrs,
    mesh_polygons,
    validate_gap_map,
    validate_surface_map,
)


_AIRBRIDGE_TOKENS = (
    "airbridge",
    "air_bridge",
    "air-bridge",
    "Airbridge",
    "AirBridge",
)


def _detect_airbridges(design: Any, surfaces_df: pd.DataFrame) -> list[str]:
    """Return human-readable hits for unsupported airbridge geometry."""
    hits: list[str] = []
    id_to_name = _component_id_to_name(design)

    for _, row in surfaces_df.iterrows():
        name = str(row["name"])
        comp = row["component"]
        comp_name = id_to_name.get(int(comp), str(comp))
        blob = f"{comp_name} {name}".lower()
        if any(tok.lower() in blob for tok in _AIRBRIDGE_TOKENS):
            hits.append(f"qgeometry ({comp_name!r}, {name!r})")

    components = getattr(design, "components", None) or {}
    for cname, component in components.items():
        cls_name = type(component).__name__
        if any(tok.lower() in cls_name.lower() for tok in _AIRBRIDGE_TOKENS):
            hits.append(f"component class {cls_name!r} ({cname!r})")
        options = getattr(component, "options", None) or {}
        try:
            keys = list(options.keys())
        except Exception:
            keys = []
        for key in keys:
            if any(tok.lower() in str(key).lower() for tok in _AIRBRIDGE_TOKENS):
                hits.append(f"component {cname!r} option {key!r}")

    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _component_id_to_name(design: Any) -> dict[int, str]:
    from .meshing import Mesh

    return Mesh._qmetal_component_id_to_name(design)


def _lookup_attr(
    mapping: Mapping[Any, Any] | None,
    component_id: Any,
    surface_name: str,
    id_to_name: dict[int, str],
) -> int | None:
    if not mapping:
        return None
    from .meshing import Mesh

    value, _key = Mesh._lookup_qm_surface_key(
        mapping, component_id, surface_name, id_to_name
    )
    if value is None:
        return None
    return int(value)


def _etch_ref_matches(
    ref: Any,
    component: Any,
    surface_name: str,
    id_to_name: dict[int, str],
) -> bool:
    """Whether a GapMap ``gaps`` entry refers to this QM etch row."""
    from .meshing import Mesh

    if isinstance(ref, str):
        return ref == surface_name
    if isinstance(ref, tuple) and len(ref) == 2:
        # Reuse Attributes-style (comp_id|comp_name, surface_name) keys.
        value, key = Mesh._lookup_qm_surface_key(
            {ref: True}, component, surface_name, id_to_name
        )
        return key is not None
    return False


def _normalize_qm_gap_map(
    gap_map: Mapping[Any, Any] | None,
    etch_meta: list[tuple[Any, str]],
    id_to_name: dict[int, str],
) -> dict[str, dict]:
    """
    Normalize a QM ``gap_map`` into the same shape as GDS GapMap:

    ``{palace_name: {"gaps": [etch_poly_index, ...], "attr": int|None}}``.

    User-facing ``gaps`` entries are qgeometry names (or Attributes-style
    ``(component, name)`` tuples) for ``subtract=True`` rows — the QM
    analogue of GDS gap ids from ``inspect_gds(gaps_only=True)``.

    Accepted entry forms (parallel to :func:`validate_gap_map`):

    - ``{"gaps": ["cross_etch", ...], "attr": 10}``
    - ``["cross_etch", ...]`` (attr auto later)
    - ``{"attr": 10}`` — shorthand: ``gaps`` defaults to ``[palace_name]``
    - ``10`` — shorthand: attr only, ``gaps=[palace_name]``
    """
    if not gap_map:
        return {}
    if not etch_meta:
        raise ValueError(
            "gap_map was provided but this design has no subtract=True "
            "(etch/gap) qgeometry to tag"
        )

    out: dict[str, dict] = {}
    for name, entry in gap_map.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"GapMap keys must be non-empty strings, got {name!r}")

        if isinstance(entry, (int, np.integer)):
            gap_refs: list[Any] = [name]
            attr: int | None = int(entry)
        elif isinstance(entry, (list, tuple, set)):
            gap_refs = list(entry)
            attr = None
        elif isinstance(entry, dict):
            attr_raw = entry.get("attr", None)
            attr = int(attr_raw) if attr_raw is not None else None
            if "gaps" in entry:
                gaps = entry["gaps"]
                if isinstance(gaps, (str, tuple)):
                    gap_refs = [gaps]
                else:
                    gap_refs = list(gaps)
            else:
                # Shorthand: palace name is the etch qgeometry name.
                gap_refs = [name]
        else:
            raise ValueError(
                f"GapMap[{name!r}] must be a dict, list of etch names, or attr int "
                "(same nomenclature as mesh_gds GapMap, with etch names instead "
                "of inspect_gds gap ids)"
            )

        if not gap_refs:
            raise ValueError(f"GapMap[{name!r}] has empty gaps list")

        gids: list[int] = []
        for ref in gap_refs:
            matched = [
                gid
                for gid, (comp, sname) in enumerate(etch_meta)
                if _etch_ref_matches(ref, comp, sname, id_to_name)
            ]
            if not matched:
                raise ValueError(
                    f"GapMap[{name!r}] gaps entry {ref!r} matched no "
                    f"subtract=True qgeometry (known etches: "
                    f"{sorted({n for _, n in etch_meta})})"
                )
            for gid in matched:
                if gid not in gids:
                    gids.append(gid)

        out[name] = {"gaps": gids, "attr": attr}
    return out


def build_qm_meshwell_layout(
    design: Any,
    *,
    Attributes: dict[str | tuple[int | str, str], int] | None = None,
    gap_map: dict | None = None,
    margin: float = 0.5,
    margin_x: float | None = None,
    margin_y: float | None = None,
    ground_plane_attr: int | str = "auto",
    auto_ground: bool = True,
) -> dict[str, Any]:
    """
    Convert a Quantum Metal design into MeshWell ``mesh_polygons`` inputs.

    - Metals (``subtract=False``): auto SurfaceMap by qgeometry **name**
      (disambiguated with component name on collision). ``Attributes``
      overrides Palace attr ids when provided.
    - Gaps / etch (``subtract=True``): tagged only via ``gap_map`` (same
      nomenclature as :func:`mesh_gds` GapMap; ``gaps`` entries are etch
      qgeometry names instead of ``inspect_gds`` ids). Untagged etches stay
      CAD-only dielectric carvers.
    - ``ground_plane``: when ``auto_ground`` (QM default), synthesized as
      ``chip_bbox − metals − etches`` and added to the SurfaceMap.
      GDS ``mesh_gds`` does **not** use this helper — no auto ground there.
    """
    from .meshing import Mesh

    surfaces_df = Mesh._collect_qm_imprint_surfaces(design).copy()
    if surfaces_df.empty:
        raise ValueError(
            "No surface geometry found in Quantum Metal design "
            "(poly + buffered path tables are empty)."
        )
    if "helper" in surfaces_df.columns:
        surfaces_df = surfaces_df[surfaces_df["helper"] == False]

    air_hits = _detect_airbridges(design, surfaces_df)
    if air_hits:
        raise NotImplementedError(
            "Airbridges are not supported on the MeshWell QM path yet "
            "(coplanar z=0 metals only). Detected: "
            + "; ".join(air_hits)
            + ". Omit/flatten airbridge geometry, or use backend='gmsh' "
            "(also coplanar — airbridges are not meshed as 3D bridges)."
        )

    if margin_x is None:
        margin_x = margin
    if margin_y is None:
        margin_y = margin

    id_to_name = _component_id_to_name(design)
    Attributes = dict(Attributes or {})
    gap_map_in = dict(gap_map or {})

    metal_groups: dict[str, list[Polygon]] = defaultdict(list)
    metal_attr_hints: dict[str, int] = {}
    etch_polys: list[Polygon] = []
    etch_meta: list[tuple[Any, str]] = []  # (component, name) per etch poly
    all_imprints: list[Polygon] = []

    # First pass: collect metals / etches; choose SurfaceMap keys.
    name_counts: dict[str, int] = defaultdict(int)
    for _, row in surfaces_df.iterrows():
        if bool(row["subtract"]):
            continue
        name_counts[str(row["name"])] += 1

    for _, row in surfaces_df.iterrows():
        name = str(row["name"])
        component = row["component"]
        geom = row["geometry"]
        parts = _flatten_polygons(geom)
        if not parts:
            continue
        all_imprints.extend(parts)
        is_subtract = bool(row["subtract"])
        if is_subtract:
            for p in parts:
                etch_polys.append(p)
                etch_meta.append((component, name))
            continue

        # Auto tag by qgeometry name; disambiguate if the same name appears
        # on multiple components (use component_name_surface_name).
        comp_name = id_to_name.get(int(component), str(component))
        if name_counts[name] > 1:
            key = f"{comp_name}_{name}"
        else:
            key = name
        metal_groups[key].extend(parts)
        hinted = _lookup_attr(Attributes, component, name, id_to_name)
        if hinted is not None:
            if key in metal_attr_hints and metal_attr_hints[key] != hinted:
                raise ValueError(
                    f"Conflicting Attributes for SurfaceMap key {key!r}: "
                    f"{metal_attr_hints[key]} vs {hinted}"
                )
            metal_attr_hints[key] = hinted

    if not metal_groups:
        raise ValueError(
            "No metal (subtract=False) surfaces found in Quantum Metal design."
        )

    # Build polygon list + SurfaceMap for metals.
    polygons: list[Polygon] = []
    surface_map: dict[str, dict] = {}
    for key in sorted(metal_groups.keys()):
        ids: list[int] = []
        for p in metal_groups[key]:
            ids.append(len(polygons))
            polygons.append(p)
        entry: dict[str, Any] = {"polygons": ids}
        if key in metal_attr_hints:
            entry["attr"] = int(metal_attr_hints[key])
        surface_map[key] = entry

    # QM etch polys often overlap their parent metals (pocket drawings).
    # MeshWell CAD subtracts gap pieces from every metal — trim etches so they
    # only cover dielectric, never metal footprints.
    metal_union = (
        unary_union([p for parts in metal_groups.values() for p in parts])
        if metal_groups
        else None
    )
    trimmed_etches: list[Polygon] = []
    trimmed_etch_meta: list[tuple[Any, str]] = []
    if etch_polys and metal_union is not None and not metal_union.is_empty:
        for poly, meta in zip(etch_polys, etch_meta):
            diff = poly.difference(metal_union)
            parts = [
                p
                for p in _flatten_polygons(diff)
                if not p.is_empty and p.area > 0
            ]
            for p in parts:
                trimmed_etches.append(p)
                trimmed_etch_meta.append(meta)
    else:
        trimmed_etches = list(etch_polys)
        trimmed_etch_meta = list(etch_meta)
    etch_polys = trimmed_etches
    etch_meta = trimmed_etch_meta

    # User gap_map (etch names) → integer-id GapMap over etch polygon list.
    gap_map = _normalize_qm_gap_map(gap_map_in, etch_meta, id_to_name)

    # QM-only auto ground: leftover chip after metals + (trimmed) etches.
    ground_ids: list[int] = []
    if auto_ground:
        ground_imprints = [p for parts in metal_groups.values() for p in parts]
        ground_imprints.extend(etch_polys)
        if not ground_imprints:
            raise ValueError("Cannot build ground_plane: no imprint polygons")
        chip = _chip_bbox(ground_imprints, float(margin_x), float(margin_y))
        imprint_union = unary_union(ground_imprints)
        ground_geom = chip.difference(imprint_union)
        ground_parts = [
            p for p in _flatten_polygons(ground_geom) if not p.is_empty and p.area > 0
        ]
        if not ground_parts:
            raise ValueError(
                "auto ground_plane was empty after subtracting metals/etches "
                "from the chip bbox; check margin and qgeometry coverage."
            )
        for p in ground_parts:
            ground_ids.append(len(polygons))
            polygons.append(p)

    # Metals first (preserve explicit Attributes ids); ground attr assigned later
    # so volumes stay substrate → air → ground → far_field.
    metal_only = assign_missing_attrs(
        validate_surface_map(surface_map, n_polygons=len(polygons))
    )
    surface_map = dict(metal_only)
    if ground_ids:
        used = {int(v["attr"]) for v in metal_only.values()}
        placeholder = (max(used) if used else 0) + 10_000
        if ground_plane_attr != "auto":
            placeholder = int(ground_plane_attr)
            if placeholder in used:
                raise ValueError(
                    f"ground_plane_attr={placeholder} collides with a metal attribute"
                )
        surface_map["ground_plane"] = {
            "polygons": ground_ids,
            "attr": int(placeholder),
        }

    if gap_map:
        gap_map = validate_gap_map(
            gap_map,
            n_gaps=len(etch_polys),
            reserved_names=set(surface_map.keys()),
        )

    return {
        "polygons": polygons,
        "surface_map": surface_map,
        "gap_map": gap_map,
        "gap_polygons": etch_polys,  # may be empty — still pass through
        "metal_keys": sorted(metal_only.keys()),
        "ground_ids": ground_ids,
        "ground_plane_attr": ground_plane_attr,
    }


def mesh_quantum_metal_meshwell(
    design: Any,
    output_mesh: str | Path = "mesh_for_pyPalace.msh",
    *,
    Attributes: dict[str | tuple[int | str, str], int] | None = None,
    gap_map: dict | None = None,
    substrate_thickness: float = 500.0,
    airbox_height: float = 500.0,
    margin: float = 500.0,
    margin_x: float | None = None,
    margin_y: float | None = None,
    volume_mesh_size: float = 250.0,
    surface_mesh_size: float = 20.0,
    custom_surface_mesh: dict[str | tuple[int | str, str], float] | None = None,
    refinement_radius: float = 150.0,
    mesh_scale: float = 1000.0,
    ground_plane_attr: int | str = "auto",
    farfield_attr: int | str = "auto",
    substrate_attr: int | str = "auto",
    air_attr: int | str = "auto",
    auto_ground: bool = True,
    fuzzy_value: float | None = None,
    identify_arcs: bool = False,
) -> pd.DataFrame:
    """
    Mesh a Quantum Metal design with the MeshWell backend.

    Auto-tags metals by qgeometry name, synthesizes ``ground_plane`` when
    ``auto_ground=True`` (QM-only; not used by ``mesh_gds``), and tags
    etch/gaps only via ``gap_map`` (same nomenclature as ``mesh_gds``).
    Length kwargs are always in **µm**; ``mesh_scale`` only converts design
    coordinates (default ``1000`` for mm → µm). Airbridges raise
    ``NotImplementedError``.
    """
    if float(mesh_scale) == 0.0:
        raise ValueError("mesh_scale must be non-zero")
    scale = float(mesh_scale)
    # Layout builder works in design-native units (typically mm); convert
    # µm margins → native before synthesizing the chip / ground plane.
    margin_native = float(margin) / scale
    margin_x_native = (
        None if margin_x is None else float(margin_x) / scale
    )
    margin_y_native = (
        None if margin_y is None else float(margin_y) / scale
    )
    layout = build_qm_meshwell_layout(
        design,
        Attributes=Attributes,
        gap_map=gap_map,
        margin=margin_native,
        margin_x=margin_x_native,
        margin_y=margin_y_native,
        ground_plane_attr=ground_plane_attr,
        auto_ground=auto_ground,
    )

    # custom_surface_mesh may use QM Attribute-style keys; resolve to SurfaceMap
    # / GapMap names (geometry name or ground_plane / far_field).
    custom_out: dict[str, float] = {}
    if custom_surface_mesh:
        id_to_name = _component_id_to_name(design)
        from .meshing import Mesh

        surfaces_df = Mesh._collect_qm_imprint_surfaces(design)
        for key, size in custom_surface_mesh.items():
            if key in ("ground_plane", "far_field"):
                custom_out[str(key)] = float(size)
                continue
            if isinstance(key, str) and key in layout["surface_map"]:
                custom_out[key] = float(size)
                continue
            if isinstance(key, str) and key in layout["gap_map"]:
                custom_out[key] = float(size)
                continue
            # try match against rows → resolved SurfaceMap/GapMap key
            matched = False
            for _, row in surfaces_df.iterrows():
                val, _ = Mesh._lookup_qm_surface_key(
                    {key: size}, row["component"], str(row["name"]), id_to_name
                )
                if val is None:
                    continue
                name = str(row["name"])
                comp_name = id_to_name.get(int(row["component"]), str(row["component"]))
                # same disambiguation as build
                n_count = int((surfaces_df["name"] == name).sum())
                resolved = f"{comp_name}_{name}" if n_count > 1 else name
                if bool(row["subtract"]):
                    if resolved in layout["gap_map"]:
                        custom_out[resolved] = float(size)
                        matched = True
                elif resolved in layout["surface_map"]:
                    custom_out[resolved] = float(size)
                    matched = True
            if not matched and isinstance(key, str):
                custom_out[key] = float(size)

    smap = dict(layout["surface_map"])
    # Legacy QM attr order: metals → substrate → air → ground_plane → far_field
    max_metal = max(
        (int(smap[k]["attr"]) for k in layout["metal_keys"]),
        default=0,
    )
    if substrate_attr == "auto":
        substrate_attr = max_metal + 1
    else:
        substrate_attr = int(substrate_attr)
    if air_attr == "auto":
        air_attr = int(substrate_attr) + 1
    else:
        air_attr = int(air_attr)
    if layout["ground_ids"]:
        g_attr = layout["ground_plane_attr"]
        if g_attr == "auto":
            g_attr = int(air_attr) + 1
        else:
            g_attr = int(g_attr)
        smap["ground_plane"] = {
            "polygons": list(layout["ground_ids"]),
            "attr": int(g_attr),
        }
        if farfield_attr == "auto":
            farfield_attr = int(g_attr) + 1
    elif farfield_attr == "auto":
        farfield_attr = int(air_attr) + 1

    gmap = dict(layout["gap_map"] or {})
    if gmap:
        gmap = assign_missing_attrs(gmap, start=int(farfield_attr) + 1)

    # Chip / ground already includes margin → do not pad again.
    return mesh_polygons(
        layout["polygons"],
        smap,
        output_mesh=output_mesh,
        substrate_thickness=substrate_thickness,
        airbox_height=airbox_height,
        margin=0.0,
        margin_x=0.0,
        margin_y=0.0,
        volume_mesh_size=volume_mesh_size,
        surface_mesh_size=surface_mesh_size,
        custom_surface_mesh=custom_out or None,
        refinement_radius=refinement_radius,
        mesh_scale=mesh_scale,
        farfield_attr=int(farfield_attr) if farfield_attr != "auto" else farfield_attr,
        substrate_attr=int(substrate_attr),
        air_attr=int(air_attr),
        gap_map=gmap or None,
        gap_polygons=layout["gap_polygons"],
        identify_arcs=identify_arcs,
        fuzzy_value=fuzzy_value,
        log_label="Quantum Metal",
    )
