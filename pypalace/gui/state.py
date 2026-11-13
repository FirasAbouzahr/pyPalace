"""Session helpers for the GDS tagger GUI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon
from shapely.ops import unary_union

from pypalace.gds_mesh import (
    enumerate_gap_pieces,
    load_gds_polygons,
    resolve_gds_layers,
)


@dataclass
class SurfaceTag:
    name: str
    polygons: list[int]
    attr: int | None = None
    union: bool = True  # GUI merges are usually intentional unions

    def to_map_entry(self) -> dict[str, Any]:
        entry: dict[str, Any] = {"polygons": list(self.polygons)}
        if self.attr is not None:
            entry["attr"] = int(self.attr)
        if self.union:
            entry["union"] = True
        return entry


@dataclass
class GapTag:
    name: str
    gaps: list[int]
    attr: int | None = None

    def to_map_entry(self) -> dict[str, Any]:
        entry: dict[str, Any] = {"gaps": list(self.gaps)}
        if self.attr is not None:
            entry["attr"] = int(self.attr)
        return entry


@dataclass
class GuiProject:
    gds_path: str = ""
    layers: list[tuple[int, int]] | None = None
    cell_name: str | None = None
    mesh_scale: float = 1.0
    surfaces: dict[str, SurfaceTag] = field(default_factory=dict)
    gaps: dict[str, GapTag] = field(default_factory=dict)
    next_attr: int = 1

    # Cached geometry (not serialized)
    polygons: list[Polygon] = field(default_factory=list, repr=False)
    gap_pieces: list[Polygon] = field(default_factory=list, repr=False)

    def load_gds(
        self,
        gds_path: str | Path,
        *,
        layers: Any = None,
        cell_name: str | None = None,
    ) -> None:
        path = Path(gds_path)
        layer_list = resolve_gds_layers(path, layers=layers, cell_name=cell_name)
        polys = load_gds_polygons(path, layers=layer_list, cell_name=cell_name)
        if not polys:
            raise ValueError(f"No polygons found in {path}")
        self.gds_path = str(path.resolve())
        self.layers = list(layer_list)
        self.cell_name = cell_name
        self.polygons = list(polys)
        self.gap_pieces = enumerate_gap_pieces(self.polygons)
        self.surfaces.clear()
        self.gaps.clear()
        self.next_attr = 1

    def used_poly_ids(self) -> set[int]:
        used: set[int] = set()
        for tag in self.surfaces.values():
            used.update(tag.polygons)
        return used

    def used_gap_ids(self) -> set[int]:
        used: set[int] = set()
        for tag in self.gaps.values():
            used.update(tag.gaps)
        return used

    def assign_surface(
        self,
        name: str,
        poly_ids: list[int],
        *,
        attr: int | None = None,
        union: bool = True,
        replace: bool = False,
    ) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Surface name must be non-empty")
        ids = sorted({int(i) for i in poly_ids})
        if not ids:
            raise ValueError("Select at least one metal polygon")
        for pid in ids:
            if pid < 0 or pid >= len(self.polygons):
                raise ValueError(f"poly id {pid} out of range")
        used = self.used_poly_ids()
        if name in self.surfaces and not replace:
            # extend existing tag
            existing = set(self.surfaces[name].polygons)
            conflict = (set(ids) - existing) & (used - existing)
            if conflict:
                raise ValueError(f"Polygons already tagged: {sorted(conflict)}")
            ids = sorted(existing | set(ids))
            attr = self.surfaces[name].attr if attr is None else attr
            union = self.surfaces[name].union or union
        else:
            conflict = set(ids) & used
            if name in self.surfaces:
                conflict -= set(self.surfaces[name].polygons)
            if conflict:
                raise ValueError(f"Polygons already tagged: {sorted(conflict)}")
            if attr is None:
                attr = self.next_attr
                self.next_attr = max(self.next_attr, int(attr) + 1)
        self.surfaces[name] = SurfaceTag(
            name=name, polygons=ids, attr=int(attr) if attr is not None else None, union=union
        )

    def assign_gap(
        self,
        name: str,
        gap_ids: list[int],
        *,
        attr: int | None = None,
        replace: bool = False,
    ) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Gap name must be non-empty")
        ids = sorted({int(i) for i in gap_ids})
        if not ids:
            raise ValueError("Select at least one gap piece")
        for gid in ids:
            if gid < 0 or gid >= len(self.gap_pieces):
                raise ValueError(f"gap id {gid} out of range")
        used = self.used_gap_ids()
        if name in self.gaps and not replace:
            existing = set(self.gaps[name].gaps)
            conflict = (set(ids) - existing) & (used - existing)
            if conflict:
                raise ValueError(f"Gaps already tagged: {sorted(conflict)}")
            ids = sorted(existing | set(ids))
            attr = self.gaps[name].attr if attr is None else attr
        else:
            conflict = set(ids) & used
            if name in self.gaps:
                conflict -= set(self.gaps[name].gaps)
            if conflict:
                raise ValueError(f"Gaps already tagged: {sorted(conflict)}")
            if attr is None:
                attr = self.next_attr
                self.next_attr = max(self.next_attr, int(attr) + 1)
        self.gaps[name] = GapTag(
            name=name, gaps=ids, attr=int(attr) if attr is not None else None
        )

    def merge_selected_polys(self, poly_ids: list[int]) -> Polygon:
        """Shapely-union selected metal polygons (preview / validation)."""
        parts = [self.polygons[int(i)] for i in poly_ids]
        if not parts:
            raise ValueError("No polygons to merge")
        merged = unary_union(parts)
        return merged

    def surface_map(self) -> dict[str, dict]:
        return {n: t.to_map_entry() for n, t in self.surfaces.items()}

    def gap_map(self) -> dict[str, dict]:
        return {n: t.to_map_entry() for n, t in self.gaps.items()}

    def export_dict(self) -> dict[str, Any]:
        return {
            "gds_path": self.gds_path,
            "layers": self.layers,
            "cell_name": self.cell_name,
            "mesh_scale": self.mesh_scale,
            "surface_map": self.surface_map(),
            "gap_map": self.gap_map(),
        }

    def export_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.export_dict(), indent=2) + "\n")
        return path

    def export_python(self, path: str | Path, *, output_mesh: str = "mesh_from_gui.msh") -> Path:
        """Write a runnable script that remeshes with the tagged maps."""
        path = Path(path)
        data = self.export_dict()
        gds = json.dumps(data["gds_path"])
        smap = json.dumps(data["surface_map"], indent=4)
        gmap = json.dumps(data["gap_map"], indent=4)
        layers = json.dumps(data["layers"])
        scale = float(data["mesh_scale"])
        cell = data["cell_name"]
        cell_arg = f", cell_name={cell!r}" if cell else ""
        body = f'''\
"""Auto-generated by pyPalace GUI — GDS tag → mesh_gds."""

from pypalace.meshing import Mesh

gds = {gds}
surface_map = {smap}
gap_map = {gmap}

mesh = Mesh()
attrs = mesh.mesh_gds(
    gds,
    surface_map,
    output_mesh={output_mesh!r},
    layers={layers},
    mesh_scale={scale}{cell_arg},
    gap_map=gap_map or None,
    # Length kwargs are always in µm:
    # substrate_thickness=500,
    # airbox_height=500,
    # volume_mesh_size=250,
    # surface_mesh_size=20,
)
print(attrs)
'''
        path.write_text(body)
        return path
