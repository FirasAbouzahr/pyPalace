"""Session helpers for the GDS tagger / mesh / Palace GUI."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shapely.geometry import box, Polygon
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
    union: bool = True

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
class PortDraft:
    """Axis-aligned port rectangle drawn on the GDS canvas (mesh units / GDS coords)."""

    name: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    attr: int | None = None
    direction: str = "+Y"
    R: float = 50.0
    excitation: bool = False

    def as_polygon(self) -> Polygon:
        return box(
            min(self.xmin, self.xmax),
            min(self.ymin, self.ymax),
            max(self.xmin, self.xmax),
            max(self.ymin, self.ymax),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "xmin": self.xmin,
            "ymin": self.ymin,
            "xmax": self.xmax,
            "ymax": self.ymax,
            "attr": self.attr,
            "direction": self.direction,
            "R": self.R,
            "excitation": self.excitation,
        }


@dataclass
class MeshSettings:
    substrate_thickness: float = 500.0
    airbox_height: float = 500.0
    margin: float = 500.0
    volume_mesh_size: float = 250.0
    surface_mesh_size: float = 20.0
    refinement_radius: float = 150.0
    output_mesh: str = "mesh_from_gui.msh"
    custom_surface_mesh: dict[str, float] = field(default_factory=dict)


@dataclass
class SimSettings:
    problem_type: str = "Electrostatic"
    output_dir: str = "palace_output"
    config_path: str = "config/gui_sim.json"
    order: int = 2
    L0: float = 1.0e-6
    path_to_palace: str = ""
    n_mpi: int = 4
    substrate_eps: float = 11.45
    substrate_loss_tan: float = 1e-7
    # name → BC kind (+ optional extras for ports already on PortDraft)
    bc_map: dict[str, str] = field(default_factory=dict)


@dataclass
class GuiProject:
    gds_path: str = ""
    layers: list[tuple[int, int]] | None = None
    cell_name: str | None = None
    mesh_scale: float = 1.0
    surfaces: dict[str, SurfaceTag] = field(default_factory=dict)
    gaps: dict[str, GapTag] = field(default_factory=dict)
    ports: dict[str, PortDraft] = field(default_factory=dict)
    next_attr: int = 1
    mesh_settings: MeshSettings = field(default_factory=MeshSettings)
    sim_settings: SimSettings = field(default_factory=SimSettings)
    last_attr_table: Any = field(default=None, repr=False)
    last_mesh_path: str = ""

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
        self.ports.clear()
        self.next_attr = 1
        self.last_attr_table = None
        self.last_mesh_path = ""

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

    def _alloc_attr(self, attr: int | None) -> int:
        if attr is None:
            attr = self.next_attr
        self.next_attr = max(self.next_attr, int(attr) + 1)
        return int(attr)

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
                attr = self._alloc_attr(None)
        self.surfaces[name] = SurfaceTag(
            name=name,
            polygons=ids,
            attr=int(attr) if attr is not None else None,
            union=union,
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
                attr = self._alloc_attr(None)
        self.gaps[name] = GapTag(
            name=name, gaps=ids, attr=int(attr) if attr is not None else None
        )

    def add_port(
        self,
        name: str,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        direction: str = "+Y",
        R: float = 50.0,
        excitation: bool = False,
        attr: int | None = None,
    ) -> PortDraft:
        name = name.strip()
        if not name:
            raise ValueError("Port name must be non-empty")
        if abs(x1 - x0) < 1e-15 or abs(y1 - y0) < 1e-15:
            raise ValueError("Port rectangle must have non-zero width and height")
        if name in self.ports:
            raise ValueError(f"Port {name!r} already exists")
        if name in self.surfaces or name in self.gaps:
            raise ValueError(f"Name {name!r} already used by a metal/gap tag")
        if attr is None:
            attr = self._alloc_attr(None)
        port = PortDraft(
            name=name,
            xmin=float(min(x0, x1)),
            ymin=float(min(y0, y1)),
            xmax=float(max(x0, x1)),
            ymax=float(max(y0, y1)),
            attr=int(attr),
            direction=direction,
            R=float(R),
            excitation=bool(excitation),
        )
        self.ports[name] = port
        self.sim_settings.bc_map.setdefault(name, "LumpedPort")
        return port

    def remove_port(self, name: str) -> None:
        self.ports.pop(name, None)
        self.sim_settings.bc_map.pop(name, None)

    def merge_selected_polys(self, poly_ids: list[int]) -> Polygon:
        parts = [self.polygons[int(i)] for i in poly_ids]
        if not parts:
            raise ValueError("No polygons to merge")
        return unary_union(parts)

    def surface_map(self) -> dict[str, dict]:
        return {n: t.to_map_entry() for n, t in self.surfaces.items()}

    def gap_map(self) -> dict[str, dict]:
        return {n: t.to_map_entry() for n, t in self.gaps.items()}

    def mesh_polygon_list(self) -> tuple[list[Polygon], dict[str, dict]]:
        """Metals + port rectangles, with surface_map indices remapped for ports."""
        polys = list(self.polygons)
        smap = self.surface_map()
        for port in self.ports.values():
            idx = len(polys)
            polys.append(port.as_polygon())
            entry: dict[str, Any] = {"polygons": [idx]}
            if port.attr is not None:
                entry["attr"] = int(port.attr)
            smap[port.name] = entry
        return polys, smap

    def export_dict(self) -> dict[str, Any]:
        return {
            "gds_path": self.gds_path,
            "layers": self.layers,
            "cell_name": self.cell_name,
            "mesh_scale": self.mesh_scale,
            "surface_map": self.surface_map(),
            "gap_map": self.gap_map(),
            "ports": {n: p.to_dict() for n, p in self.ports.items()},
            "mesh_settings": {
                "substrate_thickness": self.mesh_settings.substrate_thickness,
                "airbox_height": self.mesh_settings.airbox_height,
                "margin": self.mesh_settings.margin,
                "volume_mesh_size": self.mesh_settings.volume_mesh_size,
                "surface_mesh_size": self.mesh_settings.surface_mesh_size,
                "refinement_radius": self.mesh_settings.refinement_radius,
                "output_mesh": self.mesh_settings.output_mesh,
                "custom_surface_mesh": self.mesh_settings.custom_surface_mesh,
            },
        }

    def export_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.export_dict(), indent=2) + "\n")
        return path

    def export_python(self, path: str | Path, *, output_mesh: str | None = None) -> Path:
        path = Path(path)
        data = self.export_dict()
        ms = self.mesh_settings
        out = output_mesh or ms.output_mesh
        gds = json.dumps(data["gds_path"])
        smap = json.dumps(data["surface_map"], indent=4)
        gmap = json.dumps(data["gap_map"], indent=4)
        ports = json.dumps(data["ports"], indent=4)
        layers = json.dumps(data["layers"])
        scale = float(data["mesh_scale"])
        cell = data["cell_name"]
        cell_arg = f", cell_name={cell!r}" if cell else ""
        csm = json.dumps(ms.custom_surface_mesh or {}, indent=4)
        body = f'''\
"""Auto-generated by pyPalace GUI — GDS tag → mesh_gds."""

from pypalace.meshing import Mesh

gds = {gds}
surface_map = {smap}
gap_map = {gmap}
ports = {ports}  # drawn in GUI; mesh via mesh_polygons if needed
custom_surface_mesh = {csm}

mesh = Mesh()
attrs = mesh.mesh_gds(
    gds,
    surface_map,
    output_mesh={out!r},
    layers={layers},
    mesh_scale={scale}{cell_arg},
    gap_map=gap_map or None,
    custom_surface_mesh=custom_surface_mesh or None,
    substrate_thickness={ms.substrate_thickness},
    airbox_height={ms.airbox_height},
    margin={ms.margin},
    volume_mesh_size={ms.volume_mesh_size},
    surface_mesh_size={ms.surface_mesh_size},
    refinement_radius={ms.refinement_radius},
)
print(attrs)
'''
        path.write_text(body)
        return path

    def run_mesh(self, output_mesh: str | Path | None = None):
        """Mesh tagged metals (+ drawn ports) via mesh_polygons."""
        from pypalace.gds_mesh import mesh_polygons

        if not self.surfaces and not self.ports:
            raise ValueError("Tag at least one metal (or draw a port) before meshing")
        ms = self.mesh_settings
        out = Path(output_mesh or ms.output_mesh)
        polys, smap = self.mesh_polygon_list()
        gmap = self.gap_map() or None
        # Gaps were enumerated from GDS metals only — keep that list.
        table = mesh_polygons(
            polys,
            smap,
            output_mesh=out,
            mesh_scale=self.mesh_scale,
            gap_map=gmap,
            gap_polygons=list(self.gap_pieces) if gmap else None,
            substrate_thickness=ms.substrate_thickness,
            airbox_height=ms.airbox_height,
            margin=ms.margin,
            volume_mesh_size=ms.volume_mesh_size,
            surface_mesh_size=ms.surface_mesh_size,
            refinement_radius=ms.refinement_radius,
            custom_surface_mesh=ms.custom_surface_mesh or None,
            log_label=Path(self.gds_path).name if self.gds_path else "gui",
        )
        self.last_attr_table = table
        self.last_mesh_path = str(out.resolve())
        return table

    def named_attrs(self) -> dict[str, int]:
        """Best-effort name → attr map for BC dropdowns."""
        out: dict[str, int] = {}
        for name, tag in self.surfaces.items():
            if tag.attr is not None:
                out[name] = int(tag.attr)
        for name, tag in self.gaps.items():
            if tag.attr is not None:
                out[name] = int(tag.attr)
        for name, port in self.ports.items():
            if port.attr is not None:
                out[name] = int(port.attr)
        if self.last_attr_table is not None:
            try:
                for _, row in self.last_attr_table.iterrows():
                    n = str(row.get("Name", row.get("name", "")))
                    a = row.get("ID", row.get("attr"))
                    if n and a is not None and n not in ("", "nan"):
                        out[n] = int(a)
            except Exception:
                pass
        return out

    def build_palace_config(self) -> "Any":
        """Assemble a Config from current tags / ports / sim settings."""
        from pypalace.builder import Boundaries, Domains, Solver
        from pypalace.config import Config

        ss = self.sim_settings
        attrs = self.named_attrs()
        cfg = Config(ss.config_path)
        cfg.add_Problem(ss.problem_type, Output=ss.output_dir)
        mesh_path = self.last_mesh_path or self.mesh_settings.output_mesh
        cfg.add_Model(mesh_path, L0=ss.L0)

        # Domains: prefer post-mesh substrate/air attrs when present
        sub_attr = attrs.get("substrate", 1)
        air_attr = attrs.get("air", 2)
        materials = [
            Domains.Material(
                Attributes=[sub_attr],
                Permeability=1.0,
                Permittivity=ss.substrate_eps,
                LossTan=ss.substrate_loss_tan,
            ),
            Domains.Material([air_attr], 1.0, 1.0, 0.0),
        ]
        cfg.add_Domains(materials)

        bc_list = []
        pec_attrs: list[int] = []
        ground_attrs: list[int] = []
        absorbing_attrs: list[int] = []
        terminal_i = 1
        port_i = 1

        for name, attr in attrs.items():
            if name in ("substrate", "air", "far_field"):
                continue
            kind = ss.bc_map.get(name, "PEC")
            if kind in ("(skip)", "Skip", ""):
                continue
            if kind == "PEC":
                pec_attrs.append(attr)
            elif kind == "Ground":
                ground_attrs.append(attr)
            elif kind == "Absorbing":
                absorbing_attrs.append(attr)
            elif kind == "Terminal":
                bc_list.append(Boundaries.Terminal(Index=terminal_i, Attributes=[attr]))
                terminal_i += 1
            elif kind == "LumpedPort":
                port = self.ports.get(name)
                direction = port.direction if port else "+Y"
                R = port.R if port else 50.0
                exc = bool(port.excitation) if port else False
                bc_list.append(
                    Boundaries.LumpedPort(
                        Index=port_i,
                        Attributes=[attr],
                        Direction=direction,
                        Excitation=exc if exc else None,
                        R=R,
                    )
                )
                port_i += 1

        if pec_attrs:
            bc_list.insert(0, Boundaries.PEC(pec_attrs))
        if ground_attrs:
            bc_list.append(Boundaries.Ground(ground_attrs))
        if absorbing_attrs:
            bc_list.append(Boundaries.Absorbing(absorbing_attrs))
            # far_field often absorbing
        ff = attrs.get("far_field")
        if ff is not None and ss.bc_map.get("far_field", "Absorbing") == "Absorbing":
            if ff not in absorbing_attrs:
                bc_list.append(Boundaries.Absorbing([ff]))

        if bc_list:
            cfg.add_Boundaries(bc_list)

        # Solver block — minimal defaults by problem type
        ptype = ss.problem_type
        if ptype == "Electrostatic":
            sim = Solver.Electrostatic(Save=1)
        elif ptype == "Eigenmode":
            sim = Solver.Eigenmode(Target=5.0, N=5, Tol=1e-6, Save=1)
        elif ptype == "Driven":
            sim = Solver.Driven(MinFreq=1.0, MaxFreq=10.0, FreqStep=0.1, SaveStep=1)
        elif ptype == "Magnetostatic":
            sim = Solver.Magnetostatic(Save=1)
        else:
            raise ValueError(
                f"GUI solver defaults not wired for {ptype!r} yet — "
                "pick Electrostatic, Eigenmode, Driven, or Magnetostatic"
            )
        linear = Solver.Linear(Type="Default", KSPType="Default", Tol=1e-6, MaxIts=50)
        cfg.add_Solver(Simulation=sim, Order=ss.order, Linear=linear)

        return cfg
