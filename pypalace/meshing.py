"""
pyPalace utilities for mesh generation and mesh inspection
"""

import pandas as pd
import subprocess
import numpy as np
import json
from .config import Config

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from shapely.affinity import scale as shapely_scale
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

class Mesh:
    """Mesh I/O and Gmsh export helpers for Palace workflows."""
    
    @staticmethod
    def get_mesh_attributes(filename: str | Path):
        """
        Extract physical attribute names, IDs, and entity types from a mesh file.

        Supported mesh formats include ``.bdf`` and ``.msh`` files.

        Parameters
        ----------
        filename : str
            Path to the mesh file.

        Returns
        -------
        pandas.DataFrame
            DataFrame with columns ``Name``, ``ID``, and ``Type``.
        """

        attributes_list = []
        attributes_dict = {"Name":[],"ID":[],"Type":[]}
        
        filetype = filename[-4:]
        
        if filetype == '.bdf':
        
            attributes_start = "$ Property cards"
            attributes_end = "$ Material cards"
            on_off_switch = 0
            
            with open(filename, 'r') as f:
                for line in f:
                    if attributes_start in line:
                        on_off_switch = 1

                    if on_off_switch == 1:
                        attributes_list.append(line)

                    if attributes_end in line:
                        break
                        
                    else:
                        pass
                
                if len(attributes_list) != 0:
                    for atts in attributes_list:
                        if "$ Name:" in atts:
                            attributes_dict["Name"] += [atts[8:][:-1]]
                        elif "PSOLID" in atts:
                            attributes_dict["ID"] += [atts.split()[1]]
                            attributes_dict["Type"] += ["Volume"]
                        elif "PSHELL" in atts:
                            attributes_dict["ID"] += [atts.split()[1]]
                            attributes_dict["Type"] += ["Surface"]
                            
            # Cubit seems to create phantom (not present in the actual geometry) domains, we ignore them
            if len(attributes_dict["Name"]) != len(attributes_dict["ID"]):
                attributes_dict["ID"] = attributes_dict["ID"][:len(attributes_dict["Name"])]
                attributes_dict["Type"] = attributes_dict["Type"][:len(attributes_dict["Name"])]

        elif filetype == '.msh':
            
            attributes_start = "$PhysicalNames"
            attributes_end = "$EndPhysicalNames"
            on_off_switch = 0
            
            with open(filename, 'r') as f:
                for line in f:
                    if on_off_switch == 1:
                        attributes_list.append(line)
                    
                    if attributes_start in line:
                        on_off_switch = 1

                    if attributes_end in line:
                        break
                        
                    else:
                        pass
                
                if len(attributes_list) != 0:
                    for atts in attributes_list:
                        atts = atts.split()

                        if len(atts) == 3:
                            attributes_dict["Name"] += [atts[2].strip('"')]
                            attributes_dict["ID"] += [atts[1]]

                            if atts[0] == "2":
                                attributes_dict["Type"] += ["Surface"]
                            elif atts[0] == "3":
                                attributes_dict["Type"] += ["Volume"]
            
        return pd.DataFrame(attributes_dict,index = None)

    def _qmetal_design_unit_to_meters(design: Any) -> float:
        """Return meters per Qiskit Metal design unit.

        Qiskit Metal defaults to millimeters. This helper keeps unit handling out of
        the public API while still supporting common non-default design units.
        """

        if hasattr(design, "get_units"):
            unit = design.get_units()
        else:
            unit = getattr(design, "units", "mm")

        unit = str(unit).strip().lower()
        unit = {"μm": "um", "µm": "um"}.get(unit, unit)
        unit_to_meters = {
            "m": 1.0,
            "meter": 1.0,
            "meters": 1.0,
            "mm": 1.0e-3,
            "millimeter": 1.0e-3,
            "millimeters": 1.0e-3,
            "um": 1.0e-6,
            "micron": 1.0e-6,
            "microns": 1.0e-6,
            "nm": 1.0e-9,
            "nanometer": 1.0e-9,
            "nanometers": 1.0e-9,
        }
        if unit not in unit_to_meters:
            raise ValueError(
                f"Unsupported Qiskit Metal design units {unit!r}. "
                "Expected one of: m, mm, um, nm."
            )
        return unit_to_meters[unit]

    def mesh_Quantum_Metal_design(
        design: Any,
        output_mesh: str | Path = "mesh_for_pyPalace.msh",
        *,
        Attributes: dict[str | tuple[str, str], int] | None = None,
        substrate_thickness: float = 0.5,
        airbox_height: float = 0.5,
        margin: float = 0.5,
        volume_mesh_size: float = 0.1,
        surface_mesh_size: float = 0.005,
        refinement_radius: float = 0.05,
        mesh_scale: float = 1000.0,
        ground_plane_attr: int | str = "auto",
        farfield_attr: int | str = "auto",
        substrate_attr: int | str = "auto",
        air_attr: int | str = "auto",
        geom_tol_factor: float = 0.01):
        """Generate a Palace-ready Gmsh mesh from a Quantum Metal design.
           Only for coplanar designs.

        Parameters
        ----------
        design:
            Active Qiskit Metal design. The function reads
            ``design.qgeometry.tables["poly"]``.
        output_mesh:
            Path to the ``.msh`` file to write.
        Attributes:
            Mapping from polygon row name to Palace attribute. Keys may be either
            ``"name"`` or ``("component", "name")`` for an exact row. Rows not in
            this mapping are still imprinted, but receive no explicit surface
            physical group.
        substrate_thickness, airbox_height, margin:
            Geometry lengths in the design's units. Qiskit Metal defaults to mm.
        volume_mesh_size:
            Bulk mesh target in design units.
        surface_mesh_size:
            Mesh target on every circuit polygon face (metals and etch annuli).
        refinement_radius:
            Distance over which the background field grows from
            ``surface_mesh_size`` to ``volume_mesh_size``.
        mesh_scale:
            Multiplies all design coordinates before writing the mesh. If the
            design is in mm and Palace uses ``L0 = 1e-6`` (one mesh unit is one
            micron), use ``mesh_scale = 1000``.
        ground_plane_attr, farfield_attr:
            Integer attributes or ``"auto"``. Auto assigns these after the largest
            user-provided polygon attribute.
        substrate_attr, air_attr:
            Volume physical-group attributes.
        geom_tol_factor:
            Tolerance used for face-to-polygon classification, as a fraction of
            ``surface_mesh_size`` after scaling.
        """
        
        import gmsh
        
        
        poly_df = design.qgeometry.tables["poly"].copy()
        
        def polygon_needs_dedupe(p):
            """True if any consecutive exterior or hole vertices are identical."""
            ext = list(p.exterior.coords)[:-1]
            for i in range(len(ext)):
                if ext[i] == ext[(i + 1) % len(ext)]:
                    return True
            for interior in p.interiors:
                h = list(interior.coords)[:-1]
                for i in range(len(h)):
                    if h[i] == h[(i + 1) % len(h)]:
                        return True
            return False

        damaged_goods = []
        for _, row in poly_df.iterrows():
            g = row["geometry"]
            polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
            for p in polys:
                if polygon_needs_dedupe(p):
                    damaged_goods.append((row["component"], row["name"], row.get("subtract")))
            
        damaged_goods = np.array(damaged_goods)

        num_to_repair = len(damaged_goods)

        if num_to_repair > 0:
            print(f"USER WARNING: {num_to_repair} geometry component(s) found with one or more consecutive duplicate vertices -- repairing now for meshing")

        def dedupe_exterior(poly):
            coords = list(poly.exterior.coords)
            out = [coords[0]]
            for c in coords[1:]:
                if c != out[-1]:
                    out.append(c)
            if out[0] == out[-1]:
                out[-1] = out[0]  # keep closed ring
            holes = []
            for interior in poly.interiors:
                h = list(interior.coords)
                hout = [h[0]]
                for c in h[1:]:
                    if c != hout[-1]:
                        hout.append(c)
                holes.append(hout)
            return Polygon(out, holes)

        for fixer_upper in damaged_goods:
            comp,name,substract = fixer_upper[0],fixer_upper[1],fixer_upper[2]
            idx = poly_df[(poly_df["name"] == name) & (poly_df["helper"] == False)].index[0]
            g = poly_df.at[idx, "geometry"]
            if g.geom_type == "Polygon":
                poly_df.at[idx, "geometry"] = dedupe_exterior(g)
            else:
                poly_df.at[idx, "geometry"] = MultiPolygon([dedupe_exterior(p) for p in g.geoms])

        if num_to_repair > 0:
            print(f"{num_to_repair} geometry component(s) sucessfully repaired")


        Attributes = dict(Attributes or {})
        output_path = Path(output_mesh)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        (
            substrate_thickness,
            airbox_height,
            margin,
            volume_mesh_size,
            surface_mesh_size,
            refinement_radius,
        ) = (
            substrate_thickness * mesh_scale,
            airbox_height * mesh_scale,
            margin * mesh_scale,
            volume_mesh_size * mesh_scale,
            surface_mesh_size * mesh_scale,
            refinement_radius * mesh_scale,
        )

        geom_tol = max(1e-12, geom_tol_factor * surface_mesh_size)
        design_unit_to_meters = Mesh._qmetal_design_unit_to_meters(design)
        l0_meters = design_unit_to_meters / mesh_scale

        auto_attrs = sorted(set(Attributes.values())) if Attributes else [0]
        if substrate_attr == "auto":
            substrate_attr = auto_attrs[-1] + 1
        if air_attr == "auto":
            air_attr = int(substrate_attr) + 1
        if ground_plane_attr == "auto":
            ground_plane_attr = int(air_attr) + 1
        if farfield_attr == "auto":
            farfield_attr = int(ground_plane_attr) + 1

        substrate_attr = int(substrate_attr)
        air_attr = int(air_attr)
        ground_plane_attr = int(ground_plane_attr)
        farfield_attr = int(farfield_attr)

        if "helper" in poly_df.columns:
            poly_df = poly_df[poly_df["helper"] == False]

        def polygons_from_geometry(geom: Any) -> list[Polygon]:
            if isinstance(geom, Polygon):
                return [geom]
            if isinstance(geom, MultiPolygon):
                return list(geom.geoms)
            return []

        PolyAttributeKey = str | tuple[Any, str]
        def lookup_attr(component: Any, name: str) -> tuple[int | None, PolyAttributeKey | None]:
            if (component, name) in Attributes:
                return Attributes[(component, name)], (component, name)
            if name in Attributes:
                return Attributes[name], name
            return None, None

        records: list[dict[str, Any]] = []
        for _, row in poly_df.iterrows():
            name = str(row["name"])
            component = row["component"]
            attr, key = lookup_attr(component, name)
            is_subtract = bool(row["subtract"])

            for polygon in polygons_from_geometry(row["geometry"]):
                if mesh_scale != 1.0:
                    polygon = shapely_scale(
                        polygon, xfact=mesh_scale, yfact=mesh_scale, origin=(0.0, 0.0)
                    )
                records.append(
                    {
                        "polygon": polygon,
                        "name": name,
                        "component": component,
                        "subtract": is_subtract,
                        "attribute": attr,
                        "key": key,
                    }
                )

        if not records:
            raise ValueError('No polygon geometry found in design.qgeometry.tables["poly"].')

        warnings: list[str] = []
        present_keys = {(record["component"], record["name"]) for record in records}
        present_names = {record["name"] for record in records}
        for key in Attributes:
            if isinstance(key, tuple) and key not in present_keys:
                warnings.append(f"Attributes key {key!r} matched no poly row")
            elif isinstance(key, str) and key not in present_names:
                warnings.append(f"Attributes key {key!r} matched no poly row")

        tagged_records = [record for record in records if record["attribute"] is not None]

        bbox_geom = unary_union([record["polygon"] for record in records])
        xmin, ymin, xmax, ymax = bbox_geom.bounds
        xmin -= margin
        ymin -= margin
        xmax += margin
        ymax += margin
        dx = xmax - xmin
        dy = ymax - ymin
        z_substrate_bottom = -substrate_thickness
        bounding_box = (xmin, ymin, z_substrate_bottom, xmax, ymax, airbox_height)

        def add_polygon_surface(polygon: Polygon, z: float, lc: float) -> int:
            coords = list(polygon.exterior.coords)
            points = [
                gmsh.model.occ.addPoint(float(x), float(y), float(z), lc)
                for x, y in coords[:-1]
            ]
            lines = [
                gmsh.model.occ.addLine(points[i], points[(i + 1) % len(points)])
                for i in range(len(points))
            ]
            outer = gmsh.model.occ.addCurveLoop(lines)

            holes = []
            for interior in polygon.interiors:
                hole_coords = list(interior.coords)[::-1]
                hole_points = [
                    gmsh.model.occ.addPoint(float(x), float(y), float(z), lc)
                    for x, y in hole_coords[:-1]
                ]
                hole_lines = [
                    gmsh.model.occ.addLine(
                        hole_points[i], hole_points[(i + 1) % len(hole_points)]
                    )
                    for i in range(len(hole_points))
                ]
                holes.append(-gmsh.model.occ.addCurveLoop(hole_lines))

            return gmsh.model.occ.addPlaneSurface([outer] + holes)

        def split_volumes_by_z() -> tuple[list[int], list[int]]:
            substrate_volumes: list[int] = []
            air_volumes: list[int] = []
            for dim, tag in gmsh.model.getEntities(3):
                _, _, z = gmsh.model.occ.getCenterOfMass(dim, tag)
                (substrate_volumes if z < -geom_tol else air_volumes).append(tag)
            return substrate_volumes, air_volumes

        def outer_faces(volumes: list[int]) -> list[tuple[int, int]]:
            if not volumes:
                return []
            return [
                (dim, tag)
                for dim, tag in gmsh.model.getBoundary(
                    [(3, volume) for volume in volumes],
                    combined=True,
                    oriented=False,
                    recursive=False,
                )
                if dim == 2
            ]

        def face_boundary_xy(face_tag: int) -> list[tuple[float, float]]:
            points: list[tuple[float, float]] = []
            for dim, tag in gmsh.model.getBoundary(
                [(2, face_tag)], recursive=True, oriented=False
            ):
                if dim != 0:
                    continue
                try:
                    x, y, _ = gmsh.model.getValue(0, tag, [])
                except Exception:
                    continue
                points.append((x, y))
            return points

        def face_inside_polygon(face_tag: int, polygon: Polygon) -> bool:
            points = face_boundary_xy(face_tag)
            if not points:
                return False
            return all(polygon.distance(Point(x, y)) <= geom_tol for x, y in points)

        owns_gmsh = not gmsh.isInitialized()
        if owns_gmsh:
            gmsh.initialize()
        else:
            gmsh.clear()

        try:
            gmsh.model.add("qiskit_metal_pure_gmsh")

            substrate = gmsh.model.occ.addBox(
                xmin, ymin, z_substrate_bottom, dx, dy, substrate_thickness
            )
            airbox = gmsh.model.occ.addBox(xmin, ymin, 0.0, dx, dy, airbox_height)

            for record in records:
                record["surface_tag"] = add_polygon_surface(
                    record["polygon"], z=0.0, lc=surface_mesh_size
                )
            surface_tags = [record["surface_tag"] for record in records]

            gmsh.model.occ.fragment([(3, substrate)], [(3, airbox)])
            gmsh.model.occ.removeAllDuplicates()
            gmsh.model.occ.synchronize()
            sub_vols, air_vols = split_volumes_by_z()

            if surface_tags:
                gmsh.model.occ.fragment(
                    [(3, volume) for volume in sub_vols + air_vols],
                    [(2, tag) for tag in surface_tags],
                )
                gmsh.model.occ.removeAllDuplicates()
                gmsh.model.occ.synchronize()
                sub_vols, air_vols = split_volumes_by_z()

            all_vols = sub_vols + air_vols
            outer = outer_faces(all_vols)
            outer_set = {tag for _, tag in outer}
            records_by_area = sorted(records, key=lambda record: record["polygon"].area)

            attr_to_faces: dict[int, set[int]] = defaultdict(set)
            ground_plane_faces: set[int] = set()
            gap_faces: set[int] = set()

            for dim, tag in gmsh.model.getEntities(2):
                if tag in outer_set:
                    continue
                _, _, z = gmsh.model.occ.getCenterOfMass(dim, tag)
                if abs(z) > geom_tol:
                    continue

                matched_record = None
                for record in records_by_area:
                    if face_inside_polygon(tag, record["polygon"]):
                        matched_record = record
                        break

                if matched_record is None:
                    ground_plane_faces.add(tag)
                elif matched_record["attribute"] is not None:
                    attr_to_faces[int(matched_record["attribute"])].add(tag)
                else:
                    gap_faces.add(tag)

            farfield_faces = sorted({tag for _, tag in outer})

            if sub_vols:
                gmsh.model.addPhysicalGroup(3, sub_vols, substrate_attr)
                gmsh.model.setPhysicalName(3, substrate_attr, "substrate")
            if air_vols:
                gmsh.model.addPhysicalGroup(3, air_vols, air_attr)
                gmsh.model.setPhysicalName(3, air_attr, "air")

            attr_labels: dict[int, str] = {}
            attr_sources: dict[int, set[tuple[Any, str]]] = defaultdict(set)
            attr_is_subtract: dict[int, bool] = {}

            for record in tagged_records:
                attr = int(record["attribute"])
                label = (
                    record["name"]
                    if isinstance(record["key"], str)
                    else f"{record['component']}__{record['name']}"
                )
                attr_labels.setdefault(attr, label)
                attr_sources[attr].add((record["component"], record["name"]))
                attr_is_subtract.setdefault(attr, bool(record["subtract"]))

            for attr, faces in attr_to_faces.items():
                if not faces:
                    continue
                gmsh.model.addPhysicalGroup(2, sorted(faces), attr)
                gmsh.model.setPhysicalName(2, attr, attr_labels.get(attr, f"attr_{attr}"))

            if ground_plane_faces:
                gmsh.model.addPhysicalGroup(2, sorted(ground_plane_faces), ground_plane_attr)
                gmsh.model.setPhysicalName(2, ground_plane_attr, "ground_plane")
            else:
                warnings.append("no ground_plane faces were identified")

            if farfield_faces:
                gmsh.model.addPhysicalGroup(2, farfield_faces, farfield_attr)
                gmsh.model.setPhysicalName(2, farfield_attr, "far_field")
            else:
                warnings.append("no far_field faces were identified")

            poly_faces: set[int] = set()
            for faces in attr_to_faces.values():
                poly_faces.update(faces)
            poly_faces.update(gap_faces)

            if poly_faces:
                dist_field = gmsh.model.mesh.field.add("Distance")
                gmsh.model.mesh.field.setNumbers(
                    dist_field, "SurfacesList", sorted(poly_faces)
                )
                gmsh.model.mesh.field.setNumber(dist_field, "Sampling", 100)

                thresh_field = gmsh.model.mesh.field.add("Threshold")
                gmsh.model.mesh.field.setNumber(thresh_field, "InField", dist_field)
                gmsh.model.mesh.field.setNumber(thresh_field, "SizeMin", surface_mesh_size)
                gmsh.model.mesh.field.setNumber(thresh_field, "SizeMax", volume_mesh_size)
                gmsh.model.mesh.field.setNumber(thresh_field, "DistMin", 0.0)
                gmsh.model.mesh.field.setNumber(thresh_field, "DistMax", refinement_radius)
                gmsh.model.mesh.field.setAsBackgroundMesh(thresh_field)

            gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
            gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
            gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
            gmsh.option.setNumber("Mesh.CharacteristicLengthMin", surface_mesh_size)
            gmsh.option.setNumber("Mesh.CharacteristicLengthMax", volume_mesh_size)
            gmsh.option.setNumber("Mesh.ElementOrder", 1)
            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
            gmsh.option.setNumber("Mesh.Binary", 0)
            gmsh.option.setNumber("Mesh.SaveAll", 0)
            gmsh.option.setNumber("Mesh.Algorithm3D", 1)

            gmsh.model.mesh.generate(3)
            gmsh.write(str(output_path))

        finally:
            if owns_gmsh and gmsh.isInitialized():
                gmsh.finalize()
                
        mesh_attributes = Mesh.get_mesh_attributes(output_mesh)
        mesh_attributes = mesh_attributes.sort_values("ID")
        return mesh_attributes
