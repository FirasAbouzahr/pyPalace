"""
pyPalace utilities for mesh generation and mesh inspection
"""

import pandas as pd
import subprocess
import numpy as np
import json
import math
from .config import Config

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from shapely.affinity import scale as shapely_scale
from shapely.geometry import CAP_STYLE, JOIN_STYLE, LineString, MultiLineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

class Mesh:
    """Mesh I/O and Gmsh export helpers for Palace workflows."""

    _PLOT_MESH_SKIP_LABELS = frozenset({"air", "substrate"})
    _PLOT_MESH_COLORS = (
        "#2196F3",  # bright blue
        "#4CAF50",  # bright green
        "#F44336",  # bright red
        "#03A9F4",  # sky blue
        "#66BB6A",  # light green
        "#EF5350",  # light red
        "#1565C0",  # vivid blue
        "#2E7D32",  # green
        "#D32F2F",  # red
        "#00B0FF",  # azure
    )
    
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

        filename = str(filename)
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

    @staticmethod
    def _mesh_filetype(filename: str | Path) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in (".msh", ".bdf"):
            raise ValueError('mesh file must end in ".msh" or ".bdf"')
        return suffix

    @staticmethod
    def _plane_axes(normal: str) -> tuple[int, int]:
        if normal == "z":
            return 0, 1
        if normal == "y":
            return 0, 2
        if normal == "x":
            return 1, 2
        raise ValueError("normal must be 'x', 'y', or 'z'")

    @staticmethod
    def _split_bdf_xy_token(token: str) -> tuple[float, float]:
        if len(token) < 2:
            raise ValueError(f"could not parse BDF coordinate token {token!r}")
        for split in range(1, len(token)):
            if token[split] not in ".-+eE":
                continue
            try:
                return float(token[:split]), float(token[split:])
            except ValueError:
                continue
        raise ValueError(f"could not parse BDF coordinate token {token!r}")

    @staticmethod
    def _read_msh_for_plot(filename: str | Path):
        nodes: dict[int, tuple[float, float, float]] = {}
        tris: list[tuple[int, tuple[int, int, int]]] = []
        tets: list[tuple[int, tuple[int, int, int, int]]] = []

        section = None
        n_expected = 0
        n_read = 0

        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("$"):
                    if line == "$Nodes":
                        section = "nodes"
                        n_read = 0
                        n_expected = 0
                    elif line == "$Elements":
                        section = "elements"
                        n_read = 0
                        n_expected = 0
                    elif line.startswith("$End"):
                        section = None
                    continue

                if section == "nodes":
                    if n_expected == 0:
                        n_expected = int(line)
                        continue
                    parts = line.split()
                    nid = int(parts[0])
                    nodes[nid] = (float(parts[1]), float(parts[2]), float(parts[3]))
                    n_read += 1
                    if n_read >= n_expected:
                        section = None

                elif section == "elements":
                    if n_expected == 0:
                        n_expected = int(line)
                        continue
                    parts = line.split()
                    elm_type = int(parts[1])
                    num_tags = int(parts[2])
                    phys = int(parts[3])
                    node_start = 3 + num_tags
                    node_ids = tuple(int(x) for x in parts[node_start:])

                    if elm_type == 2 and len(node_ids) == 3:
                        tris.append((phys, node_ids))
                    elif elm_type == 4 and len(node_ids) == 4:
                        tets.append((phys, node_ids))

                    n_read += 1
                    if n_read >= n_expected:
                        section = None

        return nodes, tris, tets

    @staticmethod
    def _read_bdf_for_plot(filename: str | Path):
        nodes: dict[int, tuple[float, float, float]] = {}
        tris: list[tuple[int, tuple[int, int, int]]] = []
        tets: list[tuple[int, tuple[int, int, int, int]]] = []

        pending_id = None
        pending_xy = None
        in_bulk = False

        with open(filename, "r") as f:
            for line in f:
                if "BEGIN BULK" in line:
                    in_bulk = True
                    continue
                if not in_bulk:
                    continue

                if line.startswith("GRID*"):
                    parts = line.split()
                    pending_id = int(parts[1])
                    if len(parts) >= 5:
                        pending_xy = (float(parts[3]), float(parts[4]))
                    elif len(parts) == 4:
                        pending_xy = Mesh._split_bdf_xy_token(parts[3])
                    else:
                        pending_id = None
                        pending_xy = None

                elif line.startswith("*") and pending_id != None:
                    z = float(line.split()[1])
                    nodes[pending_id] = (pending_xy[0], pending_xy[1], z)
                    pending_id = None
                    pending_xy = None

                elif line.startswith("CTRIA3"):
                    parts = line.split()
                    pid = int(parts[2])
                    tri = (int(parts[3]), int(parts[4]), int(parts[5]))
                    tris.append((pid, tri))

                elif line.startswith("CTETRA"):
                    parts = line.split()
                    pid = int(parts[2])
                    tet = tuple(int(parts[i]) for i in range(3, 7))
                    tets.append((pid, tet))

        return nodes, tris, tets

    @staticmethod
    def _triangles_on_plane(
        nodes: dict[int, tuple[float, float, float]],
        tris: list[tuple[int, tuple[int, int, int]]],
        tets: list[tuple[int, tuple[int, int, int, int]]],
        normal: str,
        origin: tuple[float, float, float],
        tol: float,
    ) -> list[tuple[int, np.ndarray]]:
        axis = {"x": 0, "y": 1, "z": 2}[normal]
        origin_val = float(origin[axis])
        out: list[tuple[int, np.ndarray]] = []

        def on_plane(nid: int) -> bool:
            return abs(nodes[nid][axis] - origin_val) <= tol

        def add_tri(phys: int, nids: tuple[int, int, int]):
            if not (on_plane(nids[0]) and on_plane(nids[1]) and on_plane(nids[2])):
                return
            out.append(
                (
                    phys,
                    np.asarray(
                        [nodes[nids[0]], nodes[nids[1]], nodes[nids[2]]], dtype=float
                    ),
                )
            )

        for phys, nids in tris:
            add_tri(phys, nids)

        tet_faces = (
            (0, 1, 2),
            (0, 1, 3),
            (0, 2, 3),
            (1, 2, 3),
        )
        for phys, nids in tets:
            for face in tet_faces:
                add_tri(phys, (nids[face[0]], nids[face[1]], nids[face[2]]))

        return out

    @staticmethod
    def _triangle_area_2d(tri: np.ndarray) -> float:
        a, b, c = tri
        return 0.5 * abs(
            (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        )

    @staticmethod
    def _label_anchor_for_polys(polys: list[np.ndarray]) -> np.ndarray:
        """Anchor labels on the largest face in a physical group."""
        areas = [Mesh._triangle_area_2d(tri) for tri in polys]
        return polys[int(np.argmax(areas))].mean(axis=0)

    @staticmethod
    def _ray_extent_from_point(
        px: float,
        py: float,
        ux: float,
        uy: float,
        xmin: float,
        xmax: float,
        ymin: float,
        ymax: float,
    ) -> float:
        """Distance from a point to the plot boundary along a unit direction."""
        t_candidates = []
        if ux > 1e-12:
            t_candidates.append((xmax - px) / ux)
        elif ux < -1e-12:
            t_candidates.append((xmin - px) / ux)
        if uy > 1e-12:
            t_candidates.append((ymax - py) / uy)
        elif uy < -1e-12:
            t_candidates.append((ymin - py) / uy)
        if not t_candidates:
            return max(xmax - xmin, ymax - ymin, 1e-9) * 0.5
        valid = [t for t in t_candidates if t > 1e-9]
        if not valid:
            return max(xmax - xmin, ymax - ymin, 1e-9) * 0.5
        return min(valid)

    @staticmethod
    def _callout_label_position(
        anchor: np.ndarray,
        center: np.ndarray,
        xmin: float,
        xmax: float,
        ymin: float,
        ymax: float,
    ) -> np.ndarray:
        """Place a callout label inside the mesh bounds, away from its anchor."""
        span = max(xmax - xmin, ymax - ymin, 1e-9)
        inset = 0.035 * span

        cx, cy = float(center[0]), float(center[1])
        ax, ay = float(anchor[0]), float(anchor[1])
        dx, dy = ax - cx, ay - cy
        norm = float(np.hypot(dx, dy))
        if norm < 0.05 * span:
            dy = 1.0 if ay >= cy else -1.0
            dx = 0.0
            norm = 1.0
        ux, uy = dx / norm, dy / norm

        t_edge = Mesh._ray_extent_from_point(ax, ay, ux, uy, xmin, xmax, ymin, ymax)
        offset = float(np.clip(0.22 * t_edge, 0.10 * span, 0.28 * t_edge))
        pos = np.array([ax + ux * offset, ay + uy * offset])
        pos[0] = np.clip(pos[0], xmin + inset, xmax - inset)
        pos[1] = np.clip(pos[1], ymin + inset, ymax - inset)
        return pos

    @staticmethod
    def _initial_callout_positions(
        anchors: np.ndarray,
        center: np.ndarray,
        bounds: tuple[float, float, float, float],
    ) -> np.ndarray:
        """Build starting callout positions, fanning out labels near the mesh center."""
        xmin, xmax, ymin, ymax = bounds
        span = max(xmax - xmin, ymax - ymin, 1e-9)
        inset = 0.035 * span
        xmin_i, xmax_i = xmin + inset, xmax - inset
        ymin_i, ymax_i = ymin + inset, ymax - inset

        positions = np.asarray(
            [
                Mesh._callout_label_position(anchor, center, xmin, xmax, ymin, ymax)
                for anchor in anchors
            ],
            dtype=float,
        )

        center_dists = np.linalg.norm(anchors - center, axis=1)
        near_idx = np.flatnonzero(center_dists < 0.15 * span)
        if len(near_idx) > 1:
            angles = np.linspace(np.pi / 4.0, 3.0 * np.pi / 4.0, len(near_idx))
            offset = 0.16 * span
            for k, idx in enumerate(near_idx):
                positions[idx] = anchors[idx] + offset * np.array(
                    [np.cos(angles[k]), np.sin(angles[k])]
                )

        positions[:, 0] = np.clip(positions[:, 0], xmin_i, xmax_i)
        positions[:, 1] = np.clip(positions[:, 1], ymin_i, ymax_i)
        return positions

    @staticmethod
    def _spread_label_positions(
        initial: np.ndarray,
        texts: list[str],
        xspan: float,
        yspan: float,
        bounds: tuple[float, float, float, float],
        fontsize: float = 8,
        n_iter: int = 160,
    ) -> np.ndarray:
        """Separate labels that are too close, keeping them inside the mesh bounds."""
        n = len(texts)
        xmin, xmax, ymin, ymax = bounds
        if n <= 1:
            return initial.copy()

        span = max(xspan, yspan, 1e-9)
        inset = 0.035 * span
        xmin_i, xmax_i = xmin + inset, xmax - inset
        ymin_i, ymax_i = ymin + inset, ymax - inset

        pos = initial.astype(float).copy()
        preferred = pos.copy()

        char_w = span * 0.011 * (fontsize / 8.0)
        char_h = span * 0.028 * (fontsize / 8.0)
        half_sizes = np.array([[0.5 * len(t) * char_w, 0.5 * char_h] for t in texts])

        def clip_positions(points: np.ndarray) -> np.ndarray:
            points[:, 0] = np.clip(points[:, 0], xmin_i, xmax_i)
            points[:, 1] = np.clip(points[:, 1], ymin_i, ymax_i)
            return points

        max_drift = 0.30 * span

        for _ in range(n_iter):
            for i in range(n):
                for j in range(i + 1, n):
                    dx = pos[j, 0] - pos[i, 0]
                    dy = pos[j, 1] - pos[i, 1]
                    dist = float(np.hypot(dx, dy))
                    min_dist = float(
                        np.hypot(
                            half_sizes[i, 0] + half_sizes[j, 0],
                            half_sizes[i, 1] + half_sizes[j, 1],
                        )
                        + 0.04 * span
                    )
                    if dist >= min_dist:
                        continue

                    if dist > 1e-9:
                        push = 0.70 * (min_dist - dist) / 2.0
                        pos[i, 0] -= push * dx / dist
                        pos[i, 1] -= push * dy / dist
                        pos[j, 0] += push * dx / dist
                        pos[j, 1] += push * dy / dist
                    else:
                        push = 0.70 * min_dist / 2.0
                        sign = 1.0 if j > i else -1.0
                        pos[i, 1] -= push * sign
                        pos[j, 1] += push * sign

            drift = pos - preferred
            drift_dist = np.linalg.norm(drift, axis=1)
            over = drift_dist > max_drift
            if np.any(over):
                pos[over] = preferred[over] + drift[over] * (
                    max_drift / drift_dist[over, None]
                )

            pos += 0.08 * (preferred - pos)
            clip_positions(pos)

        return pos

    @staticmethod
    def _plot_mesh_component_bounds(
        groups: dict[int, list[np.ndarray]],
        name_to_phys: dict[str, int],
        component: str | list[str],
        pad_frac: float = 0.1,
    ) -> tuple[float, float, float, float]:
        """Bounding box for one or more mesh attribute names on the cut plane."""
        if isinstance(component, str):
            names = [component]
        else:
            names = list(component)

        phys_ids: list[int] = []
        for name in names:
            if name not in name_to_phys:
                known = ", ".join(sorted(name_to_phys))
                raise ValueError(
                    f"Unknown mesh component {name!r}. Known attributes: {known}"
                )
            phys_ids.append(name_to_phys[name])

        pts = np.vstack(
            [tri for pid in phys_ids for tri in groups[pid]]
        )
        xmin = float(pts[:, 0].min())
        xmax = float(pts[:, 0].max())
        ymin = float(pts[:, 1].min())
        ymax = float(pts[:, 1].max())
        pad = pad_frac * max(xmax - xmin, ymax - ymin, 1e-9)
        return xmin - pad, xmax + pad, ymin - pad, ymax + pad

    @staticmethod
    def _group_in_view(
        polys: list[np.ndarray],
        xmin: float,
        xmax: float,
        ymin: float,
        ymax: float,
    ) -> bool:
        """Return True if any triangle from the group lies inside the viewport."""
        for tri in polys:
            inside = (
                (tri[:, 0] >= xmin)
                & (tri[:, 0] <= xmax)
                & (tri[:, 1] >= ymin)
                & (tri[:, 1] <= ymax)
            )
            if np.any(inside):
                return True
        return False

    @staticmethod
    def _plot_mesh_crop_bounds(
        center: tuple[float, float],
        span: float,
        full_bounds: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        """Square viewport centered on ``center`` with half-width ``span``."""
        if span <= 0:
            raise ValueError("crop span must be positive.")

        cx, cy = (float(center[0]), float(center[1]))
        half = float(span)
        xmin, xmax, ymin, ymax = (
            cx - half,
            cx + half,
            cy - half,
            cy + half,
        )
        fxmin, fxmax, fymin, fymax = full_bounds
        return (
            max(xmin, fxmin),
            min(xmax, fxmax),
            max(ymin, fymin),
            min(ymax, fymax),
        )

    @staticmethod
    def plot_mesh(
        meshfile,
        labeling=False,
        normal="z",
        origin=(0, 0, 0),
        tol=None,
        zoom_to_component=None,
        crop=None,
        show=True,
        save=None,
    ):
        """
        Plot a 2D cut through a Palace mesh, colored by physical attribute.

        Parameters
        ----------
        meshfile : str or Path
            Path to a ``.msh`` or ``.bdf`` mesh file.
        labeling : bool, optional
            If True, annotate selected physical groups with callout labels and
            arrows. Volume labels ``air`` and ``substrate`` are omitted.
        normal : str, optional
            Normal of the cut plane. One of ``"x"``, ``"y"``, or ``"z"``.
            Default is ``"z"`` (xy view at the metal layer).
        origin : tuple, optional
            Point on the cut plane. Default is ``(0, 0, 0)``.
        tol : float or None, optional
            Distance from the plane within which elements are included.
            Default is ``1e-3`` times the mesh bounding-box span.
        zoom_to_component : str or list of str, optional
            Crop the view to the bounding box of one or more mesh attribute
            names, with a small padding margin.
        crop : tuple, optional
            Square viewport given as ``(center, span)``, where ``center`` is
            ``(x, y)`` in plot coordinates and ``span`` is the half-width of
            the square window.
        show : bool, optional
            If True (default), display the plot.
        save : str or None, optional
            If set, save the figure to this path.
        """
        import matplotlib.pyplot as plt
        from matplotlib.collections import PolyCollection

        meshfile = Path(meshfile)
        filetype = Mesh._mesh_filetype(meshfile)

        if filetype == ".msh":
            nodes, tris, tets = Mesh._read_msh_for_plot(meshfile)
        else:
            nodes, tris, tets = Mesh._read_bdf_for_plot(meshfile)

        if not nodes:
            raise ValueError(f"No nodes found in mesh file {meshfile}")

        coords = np.asarray(list(nodes.values()), dtype=float)
        span = float(np.max(coords.max(axis=0) - coords.min(axis=0)))
        if tol == None:
            tol = max(1e-9, 1e-3 * span)

        origin = tuple(float(x) for x in origin)
        sliced = Mesh._triangles_on_plane(nodes, tris, tets, normal, origin, tol)

        if not sliced:
            axis = {"x": 0, "y": 1, "z": 2}[normal]
            raise ValueError(
                f"No mesh faces found on the cut plane {normal}={origin[axis]:g} "
                f"(tol={tol:g}). Try adjusting origin or tol."
            )

        i_ax, j_ax = Mesh._plane_axes(normal)
        attr_df = Mesh.get_mesh_attributes(str(meshfile))
        id_to_name = {
            str(row.ID): str(row.Name) for _, row in attr_df.iterrows()
        }
        name_to_phys = {name: int(pid) for pid, name in id_to_name.items()}

        groups: dict[int, list[np.ndarray]] = defaultdict(list)
        for phys, tri in sliced:
            groups[int(phys)].append(tri[:, [i_ax, j_ax]])

        all_pts = np.vstack([tri[:, [i_ax, j_ax]] for _, tri in sliced])
        full_xmin = float(all_pts[:, 0].min())
        full_xmax = float(all_pts[:, 0].max())
        full_ymin = float(all_pts[:, 1].min())
        full_ymax = float(all_pts[:, 1].max())
        full_bounds = (full_xmin, full_xmax, full_ymin, full_ymax)

        if zoom_to_component != None and crop != None:
            raise ValueError("Use only one of zoom_to_component or crop.")
        if zoom_to_component != None:
            xmin, xmax, ymin, ymax = Mesh._plot_mesh_component_bounds(
                groups, name_to_phys, zoom_to_component
            )
        elif crop != None:
            if (
                not isinstance(crop, (tuple, list))
                or len(crop) != 2
            ):
                raise ValueError("crop must be a tuple (center, span).")
            center, span = crop
            xmin, xmax, ymin, ymax = Mesh._plot_mesh_crop_bounds(
                center, span, full_bounds
            )
        else:
            xmin, xmax, ymin, ymax = full_bounds

        fig, ax = plt.subplots()
        colors = Mesh._PLOT_MESH_COLORS
        phys_ids = sorted(groups.keys())
        label_specs: list[tuple[np.ndarray, str]] = []

        for idx, phys in enumerate(phys_ids):
            polys = groups[phys]
            color = colors[idx % len(colors)]
            ax.add_collection(
                PolyCollection(
                    polys,
                    facecolors=[color],
                    edgecolors="0.25",
                    linewidths=0.15,
                    alpha=0.88,
                )
            )

            if labeling == True:
                label = id_to_name.get(str(phys), f"ID {phys}")
                if label in Mesh._PLOT_MESH_SKIP_LABELS:
                    continue
                if not Mesh._group_in_view(polys, xmin, xmax, ymin, ymax):
                    continue
                anchor = Mesh._label_anchor_for_polys(polys)
                anchor = np.array(
                    [
                        np.clip(anchor[0], xmin, xmax),
                        np.clip(anchor[1], ymin, ymax),
                    ]
                )
                label_specs.append((anchor, label))

        xspan = xmax - xmin
        yspan = ymax - ymin
        view_center = np.array([(xmin + xmax) / 2.0, (ymin + ymax) / 2.0])

        if labeling == True and label_specs:
            bounds = (xmin, xmax, ymin, ymax)
            anchors = np.asarray([anchor for anchor, _ in label_specs])
            callouts = Mesh._initial_callout_positions(anchors, view_center, bounds)
            texts = [text for _, text in label_specs]
            positions = Mesh._spread_label_positions(
                callouts, texts, xspan, yspan, bounds
            )
            label_bbox = dict(
                boxstyle="round,pad=0.2",
                facecolor="white",
                edgecolor="0.8",
                alpha=0.9,
                linewidth=0.5,
            )
            arrowprops = dict(
                arrowstyle="->",
                color="0.35",
                lw=0.8,
                shrinkA=4,
                shrinkB=3,
            )
            for (anchor, text), pos in zip(label_specs, positions):
                ax.annotate(
                    text,
                    xy=anchor,
                    xytext=pos,
                    fontsize=8,
                    ha="center",
                    va="center",
                    color="black",
                    clip_on=False,
                    arrowprops=arrowprops,
                    bbox=label_bbox,
                )

        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel(["x", "y", "z"][i_ax])
        ax.set_ylabel(["x", "y", "z"][j_ax])
        plane_axis = {"x": 0, "y": 1, "z": 2}[normal]
        title = f"Mesh cut: {normal} = {origin[plane_axis]:g}"
        if zoom_to_component != None:
            if isinstance(zoom_to_component, str):
                title += f"  |  {zoom_to_component}"
            else:
                title += "  |  " + ", ".join(zoom_to_component)
        elif crop != None:
            cx, cy = crop[0]
            title += f"  |  crop ({cx:g}, {cy:g}), span {float(crop[1]):g}"
        ax.set_title(title)

        if save != None:
            fig.savefig(save, bbox_inches="tight")
        if show == True:
            plt.show()
        else:
            plt.close(fig)

    @staticmethod
    def _parse_qmetal_length(value: Any, design: Any) -> float:
        """Parse a Qiskit Metal length into design units (mm by default)."""
        if value is None or (isinstance(value, float) and np.isnan(value)):
            raise ValueError("Missing length value for path geometry.")

        if isinstance(value, (int, float, np.floating, np.integer)):
            return float(value)

        text = str(value).strip().lower().replace(" ", "")
        text = text.replace("μm", "um").replace("µm", "um")

        suffixes = {
            "m": 1.0,
            "meter": 1.0,
            "meters": 1.0,
            "mm": 1e-3,
            "millimeter": 1e-3,
            "millimeters": 1e-3,
            "um": 1e-6,
            "micron": 1e-6,
            "microns": 1e-6,
            "nm": 1e-9,
            "nanometer": 1e-9,
            "nanometers": 1e-9,
        }

        for suffix, meters_per_unit in sorted(
            suffixes.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if text.endswith(suffix):
                number = float(text[: -len(suffix)])
                meters = number * meters_per_unit
                design_meters = Mesh._qmetal_design_unit_to_meters(design)
                return meters / design_meters

        return float(text)

    @staticmethod
    def _parse_qmetal_fillet(value: Any, design: Any) -> float:
        """Return fillet radius in design units; 0 means no fillet."""
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return 0.0
        if isinstance(value, (int, float, np.floating, np.integer)):
            return max(0.0, float(value))
        return max(0.0, Mesh._parse_qmetal_length(value, design))

    @staticmethod
    def _fillet_linestring(
        line: LineString,
        fillet: float,
        design: Any,
        *,
        resolution: int = 16,
    ) -> LineString:
        """Round path corners the same way QM's MPL renderer does."""
        if fillet <= 0 or line.is_empty or len(line.coords) <= 2:
            return line

        try:
            from qiskit_metal.renderers.renderer_mpl.mpl_renderer import QMplRenderer

            renderer = QMplRenderer(design)
            renderer.options.resolution = str(resolution)
            row = pd.Series({"geometry": line, "fillet": float(fillet)})
            filleted = renderer.fillet_path(row)
            if isinstance(filleted, LineString) and not filleted.is_empty:
                return filleted
        except Exception as exc:
            print(
                "USER WARNING: Could not apply QM fillet to path; "
                f"using sharp corners. ({exc})"
            )

        return line

    @staticmethod
    def _line_like_to_polygons(
        geom: Any,
        width: float,
        *,
        fillet: Any = None,
        design: Any | None = None,
        path_resolution: int = 16,
    ) -> list[Polygon]:
        """Buffer a QM path centerline into imprintable polygon sheet(s)."""
        if width <= 0:
            raise ValueError(f"Path width must be positive, got {width!r}.")

        if geom is None or geom.is_empty:
            return []

        if geom.geom_type == "LineString":
            lines = [geom]
        elif geom.geom_type == "MultiLineString":
            lines = list(geom.geoms)
        else:
            raise ValueError(
                f"Expected LineString or MultiLineString for path geometry, got {geom.geom_type!r}."
            )

        fillet_radius = 0.0
        if design is not None:
            fillet_radius = Mesh._parse_qmetal_fillet(fillet, design)

        polygons: list[Polygon] = []
        for line in lines:
            if line.is_empty:
                continue

            if fillet_radius > 0 and design is not None:
                line = Mesh._fillet_linestring(
                    line,
                    fillet_radius,
                    design,
                    resolution=path_resolution,
                )

            buffered = line.buffer(
                width / 2.0,
                cap_style=CAP_STYLE.flat,
                join_style=JOIN_STYLE.mitre,
                quad_segs=int(path_resolution),
            )

            if buffered.is_empty:
                continue
            if isinstance(buffered, Polygon):
                polygons.append(buffered)
            elif isinstance(buffered, MultiPolygon):
                polygons.extend(buffered.geoms)

        return polygons

    @staticmethod
    def _qmetal_component_id_to_name(design: Any) -> dict[int, str]:
        """Map QM internal component IDs to user-facing names."""
        mapping: dict[int, str] = {}
        components = getattr(design, "components", None)
        if components is None:
            return mapping

        for name, component in components.items():
            comp_id = getattr(component, "id", None)
            if comp_id is None:
                continue
            mapping[int(comp_id)] = str(name)

        return mapping

    @staticmethod
    def _qmetal_component_name_to_id(design: Any) -> dict[str, int]:
        """Map QM user-facing component names to internal IDs."""
        id_to_name = Mesh._qmetal_component_id_to_name(design)
        return {name: comp_id for comp_id, name in id_to_name.items()}

    @staticmethod
    def _lookup_qm_surface_key(
        mapping: Mapping[Any, Any],
        component_id: Any,
        surface_name: str,
        id_to_name: dict[int, str],
    ) -> tuple[Any | None, str | tuple[Any, str] | None]:
        """Match a QM surface row against an Attributes/custom_surface_mesh map."""
        comp_id = int(component_id)
        comp_name = id_to_name.get(comp_id)
        tuple_keys: list[tuple[Any, str]] = [(comp_id, surface_name)]
        if comp_name is not None:
            tuple_keys.append((comp_name, surface_name))
        for key in tuple_keys:
            if key in mapping:
                return mapping[key], key
        if surface_name in mapping:
            return mapping[surface_name], surface_name
        return None, None

    @staticmethod
    def _qm_surface_key_matches_row(
        key: Any,
        *,
        present_id_name_pairs: set[tuple[Any, str]],
        present_names: set[str],
        name_to_id: dict[str, int],
        domain_keys: frozenset[str] = frozenset(),
    ) -> bool:
        """Return whether a user-supplied surface key exists in the design."""
        if key in domain_keys:
            return True
        if isinstance(key, str):
            return key in present_names
        if not isinstance(key, tuple) or len(key) != 2:
            return False
        comp_key, surface_name = key
        if isinstance(comp_key, int):
            comp_id = comp_key
        elif isinstance(comp_key, str):
            comp_id = name_to_id.get(comp_key)
            if comp_id is None:
                return False
        else:
            return False
        return (comp_id, surface_name) in present_id_name_pairs

    @staticmethod
    def _qmetal_physical_surface_name(
        component_id: Any,
        surface_name: str,
        key: str | tuple[Any, str] | None,
        id_to_name: dict[int, str],
    ) -> str:
        """Build ``component_name_surface_name`` labels for tuple-keyed surfaces."""
        if isinstance(key, str):
            return surface_name
        comp_name = id_to_name.get(int(component_id))
        if comp_name is None:
            comp_name = str(component_id)
        return f"{comp_name}_{surface_name}"

    @dataclass(frozen=True)
    class BoundarySimplifySettings:
        """Heuristic short-edge run merging for polygon imprint boundaries."""

        min_edges: int = 10
        cluster_span: float | None = None
        short_edge: float | None = None
        smooth_angle_deg: float = 35.0
        max_deviation: float | None = None

    @staticmethod
    def _resolve_boundary_simplify_settings(
        settings: "Mesh.BoundarySimplifySettings",
        surface_mesh_size: float,
        mesh_scale: float,
        finest_surface_mesh_size: float | None = None,
    ) -> "Mesh.BoundarySimplifySettings":
        """Fill automatic span/edge/deviation defaults in scaled mesh units."""
        if finest_surface_mesh_size is None:
            finest_surface_mesh_size = surface_mesh_size

        cluster_span = settings.cluster_span
        if cluster_span is None:
            cluster_span = max(
                5.0 * finest_surface_mesh_size,
                0.1 * mesh_scale,
            )
        short_edge = settings.short_edge
        if short_edge is None:
            short_edge = max(
                2.0 * finest_surface_mesh_size,
                cluster_span / 4.0,
            )
        max_deviation = settings.max_deviation
        if max_deviation is None:
            max_deviation = max(
                0.5 * cluster_span,
                2.0 * finest_surface_mesh_size,
            )
        return Mesh.BoundarySimplifySettings(
            min_edges=settings.min_edges,
            cluster_span=cluster_span,
            short_edge=short_edge,
            smooth_angle_deg=settings.smooth_angle_deg,
            max_deviation=max_deviation,
        )

    @staticmethod
    def _xy_dist(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(b[0] - a[0], b[1] - a[1])

    @staticmethod
    def _deflection_angle_deg(
        a: tuple[float, float],
        b: tuple[float, float],
        c: tuple[float, float],
    ) -> float:
        """Return how much the polyline deflects at ``b`` when walking a -> b -> c."""
        interior = Mesh._turn_angle_deg(a, b, c)
        if interior > 90.0:
            return 180.0 - interior
        return interior

    @staticmethod
    def _turn_angle_deg(
        a: tuple[float, float],
        b: tuple[float, float],
        c: tuple[float, float],
    ) -> float:
        v1x, v1y = a[0] - b[0], a[1] - b[1]
        v2x, v2y = c[0] - b[0], c[1] - b[1]
        n1 = math.hypot(v1x, v1y)
        n2 = math.hypot(v2x, v2y)
        if n1 <= 1e-15 or n2 <= 1e-15:
            return 0.0
        cosang = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (n1 * n2)))
        return math.degrees(math.acos(cosang))

    @staticmethod
    def _is_colinear_chain(
        points: list[tuple[float, float]], tol_deg: float = 3.0
    ) -> bool:
        if len(points) <= 2:
            return True
        for idx in range(1, len(points) - 1):
            if (
                Mesh._turn_angle_deg(
                    points[idx - 1], points[idx], points[idx + 1]
                )
                > tol_deg
            ):
                return False
        return True

    @staticmethod
    def _subsample_polyline_points(
        points: list[tuple[float, float]], max_points: int = 12
    ) -> list[tuple[float, float]]:
        if len(points) <= max_points:
            return points
        indices = np.linspace(0, len(points) - 1, max_points, dtype=int)
        out: list[tuple[float, float]] = []
        for idx in indices:
            pt = points[int(idx)]
            if not out or pt != out[-1]:
                out.append(pt)
        return out

    @staticmethod
    def _chain_max_deviation(chain: list[tuple[float, float]]) -> float:
        if len(chain) <= 2:
            return 0.0
        if Mesh._is_colinear_chain(chain):
            return 0.0
        chord = LineString([chain[0], chain[-1]])
        return max(Point(xy).distance(chord) for xy in chain[1:-1])

    @staticmethod
    def _decompose_ring_to_chains(
        vertices: list[tuple[float, float]],
        settings: "Mesh.BoundarySimplifySettings",
    ) -> list[list[tuple[float, float]]]:
        """Merge consecutive short edges into spline/line chains on a closed ring."""
        n = len(vertices)
        if n < 2:
            return []

        chains: list[list[tuple[float, float]]] = []
        edges_processed = 0
        start = 0

        while edges_processed < n:
            j = start
            chain = [vertices[start]]
            total_len = 0.0
            edge_count = 0

            while True:
                k = (j + 1) % n
                edge_len = Mesh._xy_dist(vertices[j], vertices[k])

                if edge_len > settings.short_edge:
                    if edge_count == 0:
                        chains.append([vertices[start], vertices[k]])
                        edges_processed += 1
                        start = (start + 1) % n
                        edge_count = -1
                    break

                if edge_count > 0:
                    if total_len + edge_len > settings.cluster_span:
                        break
                    turn = Mesh._deflection_angle_deg(
                        vertices[(j - 1) % n], vertices[j], vertices[k]
                    )
                    if turn > settings.smooth_angle_deg:
                        break

                edge_count += 1
                total_len += edge_len
                j = k
                chain.append(vertices[k])

                if edge_count >= n:
                    break

            if edge_count == -1:
                continue

            if edge_count >= settings.min_edges:
                deviation = Mesh._chain_max_deviation(chain)
                if deviation <= settings.max_deviation:
                    chains.append(chain)
                    edges_processed += edge_count
                    start = j % n
                    continue

            chains.append([vertices[start], vertices[(start + 1) % n]])
            edges_processed += 1
            start = (start + 1) % n

        return chains

    @staticmethod
    def _gmsh_add_curve_chain(
        gmsh: Any,
        points: list[tuple[float, float]],
        z: float,
        lc: float,
    ) -> int:
        if len(points) < 2:
            raise ValueError("curve chain requires at least two points")

        if len(points) == 2 or Mesh._is_colinear_chain(points):
            p0 = gmsh.model.occ.addPoint(
                float(points[0][0]), float(points[0][1]), float(z), lc
            )
            p1 = gmsh.model.occ.addPoint(
                float(points[-1][0]), float(points[-1][1]), float(z), lc
            )
            return gmsh.model.occ.addLine(p0, p1)

        spline_pts = Mesh._subsample_polyline_points(points)
        point_tags = [
            gmsh.model.occ.addPoint(float(x), float(y), float(z), lc)
            for x, y in spline_pts
        ]
        return gmsh.model.occ.addSpline(point_tags)

    @staticmethod
    def _gmsh_add_polygon_surface(
        gmsh: Any,
        polygon: Polygon,
        z: float,
        lc: float,
        boundary_simplify: "Mesh.BoundarySimplifySettings | None" = None,
        scaled_surface_mesh_size: float | None = None,
        finest_surface_mesh_size: float | None = None,
        mesh_scale: float = 1.0,
        simplify_stats: dict[str, int] | None = None,
    ) -> int:
        if scaled_surface_mesh_size is None:
            scaled_surface_mesh_size = lc
        if finest_surface_mesh_size is None:
            finest_surface_mesh_size = scaled_surface_mesh_size

        def wire_from_ring(coords: list[tuple[float, float]], reverse: bool) -> int:
            ring = list(coords[:-1]) if len(coords) > 1 and coords[0] == coords[-1] else list(coords)
            if reverse:
                ring = ring[::-1]
            if boundary_simplify is not None:
                settings = Mesh._resolve_boundary_simplify_settings(
                    boundary_simplify,
                    scaled_surface_mesh_size,
                    mesh_scale,
                    finest_surface_mesh_size=finest_surface_mesh_size,
                )
                chains = Mesh._decompose_ring_to_chains(ring, settings)
                if simplify_stats is not None:
                    simplify_stats["polygon_edges"] = (
                        simplify_stats.get("polygon_edges", 0) + len(ring)
                    )
                    simplify_stats["gmsh_curves"] = (
                        simplify_stats.get("gmsh_curves", 0) + len(chains)
                    )
                    simplify_stats["merged_runs"] = simplify_stats.get(
                        "merged_runs", 0
                    ) + sum(1 for chain in chains if len(chain) > 2)
            else:
                chains = [
                    [ring[i], ring[(i + 1) % len(ring)]]
                    for i in range(len(ring))
                ]
            curves = [
                Mesh._gmsh_add_curve_chain(gmsh, chain, z, lc) for chain in chains
            ]
            return gmsh.model.occ.addCurveLoop(curves)

        outer = wire_from_ring(list(polygon.exterior.coords), reverse=False)

        holes = []
        for interior in polygon.interiors:
            hole_coords = list(interior.coords)[::-1]
            holes.append(-wire_from_ring(hole_coords, reverse=False))

        return gmsh.model.occ.addPlaneSurface([outer] + holes)

    @staticmethod
    def _collect_qm_imprint_surfaces(design: Any) -> pd.DataFrame:
        """
        Internal: merge QM ``poly`` rows with buffered ``path`` rows.

        Path centerlines are filleted (when ``fillet`` is set) then buffered
        to polygons before meshing. Returns QM-native columns, including
        ``component`` (internal component ID).
        """
        tables = design.qgeometry.tables
        poly_df = tables["poly"].copy() if "poly" in tables else pd.DataFrame()
        path_df = tables["path"].copy() if "path" in tables else pd.DataFrame()

        rows: list[dict[str, Any]] = []
        columns = [
            "component",
            "name",
            "geometry",
            "layer",
            "subtract",
            "helper",
            "chip",
            "fillet",
        ]

        if not poly_df.empty:
            for _, row in poly_df.iterrows():
                rows.append(
                    {
                        "component": row["component"],
                        "name": str(row["name"]),
                        "geometry": row["geometry"],
                        "layer": row.get("layer", 1),
                        "subtract": bool(row.get("subtract", False)),
                        "helper": bool(row.get("helper", False)),
                        "chip": row.get("chip", "main"),
                        "fillet": row.get("fillet", np.nan),
                    }
                )

        path_warnings: list[str] = []
        if not path_df.empty:
            for _, row in path_df.iterrows():
                name = str(row["name"])
                component = row["component"]
                try:
                    width = Mesh._parse_qmetal_length(row.get("width"), design)
                    polygons = Mesh._line_like_to_polygons(
                        row["geometry"],
                        width,
                        fillet=row.get("fillet"),
                        design=design,
                    )
                except Exception as exc:
                    path_warnings.append(
                        f"Skipped path ({component!r}, {name!r}): {exc}"
                    )
                    continue

                if not polygons:
                    path_warnings.append(
                        f"Skipped empty buffered path ({component!r}, {name!r})."
                    )
                    continue

                geometry = (
                    polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
                )
                rows.append(
                    {
                        "component": component,
                        "name": name,
                        "geometry": geometry,
                        "layer": row.get("layer", 1),
                        "subtract": bool(row.get("subtract", False)),
                        "helper": bool(row.get("helper", False)),
                        "chip": row.get("chip", "main"),
                        "fillet": row.get("fillet", np.nan),
                    }
                )

        if path_warnings:
            print("USER WARNING: " + "; ".join(path_warnings))

        if not rows:
            return pd.DataFrame(columns=columns)

        return pd.DataFrame(rows)[columns]

    @staticmethod
    def get_quantum_metal_surfaces(design: Any) -> pd.DataFrame:
        """
        User-facing table of imprintable surfaces (pads, CPW, resonators).

        Use this to choose ``Attributes`` names and to see metal vs etch.
        Does not affect meshing internals.
        """
        surfaces = Mesh._collect_qm_imprint_surfaces(design)
        if surfaces.empty:
            return pd.DataFrame(
                columns=["component_id", "component_name", "name", "subtract"]
            )

        id_to_name = Mesh._qmetal_component_id_to_name(design)

        friendly = pd.DataFrame(
            {
                "component_id": surfaces["component"].astype(int),
                "component_name": surfaces["component"].astype(int).map(id_to_name),
                "name": surfaces["name"].astype(str),
                "subtract": surfaces["subtract"].astype(bool),
            }
        )
        return friendly


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
        Attributes: dict[str | tuple[int | str, str], int] | None = None,
        substrate_thickness: float = 0.5,
        airbox_height: float = 0.5,
        margin: float = 0.5,
        margin_x: float | None = None,
        margin_y: float | None = None,
        volume_mesh_size: float = 0.25,
        surface_mesh_size: float = 0.02,
        custom_surface_mesh: dict[str | tuple[int | str, str], float] | None = None,
        refinement_radius: float = 0.15,
        mesh_scale: float = 1000.0,
        ground_plane_attr: int | str = "auto",
        farfield_attr: int | str = "auto",
        substrate_attr: int | str = "auto",
        air_attr: int | str = "auto",
        geom_tol_factor: float = 0.01,
        boundary_simplify: "Mesh.BoundarySimplifySettings | None" = None,
    ):
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
            Mapping from polygon row name to Palace attribute. Keys may be
            ``"name"``, ``(component_id, "name")``, or ``("component_name", "name")``.
            Rows not in this mapping are still imprinted, but receive no explicit
            surface physical group. Tuple-keyed surfaces are named
            ``component_name_surface_name`` in the mesh file.
        substrate_thickness, airbox_height:
            Geometry lengths in the design's units. Qiskit Metal defaults to mm.
        margin:
            Padding added to the layout bounding box on all sides when
            ``margin_x`` and ``margin_y`` are not set.
        margin_x, margin_y:
            Padding in x and y added to the layout bounding box before building
            the substrate and air box. Default to ``margin`` when omitted.
        volume_mesh_size:
            Bulk mesh target in design units. Default is coarse; Palace AMR can
            refine further during the solve.
        surface_mesh_size:
            Default mesh target on circuit polygon faces (metals and etch annuli).
        custom_surface_mesh:
            Optional per-surface mesh size overrides keyed like ``Attributes``.
            Special keys ``"ground_plane"`` and ``"far_field"`` may also be set;
            when omitted, those surfaces do not drive a local refinement field
            (bulk sizing uses ``volume_mesh_size`` away from circuit metals).
            Unlisted surfaces use ``surface_mesh_size``.
        refinement_radius:
            Distance over which the background field grows from the local surface
            mesh size to ``volume_mesh_size``.
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
            the finest surface mesh size after scaling.
        boundary_simplify:
            Optional short-edge run merging for imprint polygon boundaries.
            Experimental; use :meth:`mesh_Quantum_Metal_design_v2` for defaults.
        """
        
        import gmsh

        surfaces_df = Mesh._collect_qm_imprint_surfaces(design).copy()

        def polygon_needs_dedupe(p: Polygon) -> bool:
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

        damaged_goods: list[tuple[Any, str, Any]] = []
        for _, row in surfaces_df.iterrows():
            g = row["geometry"]
            polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
            for p in polys:
                if polygon_needs_dedupe(p):
                    damaged_goods.append(
                        (row["component"], row["name"], row.get("subtract"))
                    )

        num_to_repair = len(damaged_goods)
        if num_to_repair > 0:
            print(
                "USER WARNING: "
                f"{num_to_repair} geometry component(s) found with one or more "
                "consecutive duplicate vertices -- repairing now for meshing"
            )

        def dedupe_exterior(poly: Polygon) -> Polygon:
            coords = list(poly.exterior.coords)
            out = [coords[0]]
            for c in coords[1:]:
                if c != out[-1]:
                    out.append(c)
            if out[0] == out[-1]:
                out[-1] = out[0]
            holes = []
            for interior in poly.interiors:
                h = list(interior.coords)
                hout = [h[0]]
                for c in h[1:]:
                    if c != hout[-1]:
                        hout.append(c)
                holes.append(hout)
            return Polygon(out, holes)

        for component, name, _subtract in damaged_goods:
            mask = (
                (surfaces_df["name"] == name)
                & (surfaces_df["component"] == component)
                & (surfaces_df["helper"] == False)
            )
            idx = surfaces_df.loc[mask].index[0]
            g = surfaces_df.at[idx, "geometry"]
            if g.geom_type == "Polygon":
                surfaces_df.at[idx, "geometry"] = dedupe_exterior(g)
            else:
                surfaces_df.at[idx, "geometry"] = MultiPolygon(
                    [dedupe_exterior(p) for p in g.geoms]
                )

        if num_to_repair > 0:
            print(f"{num_to_repair} geometry component(s) sucessfully repaired")

        Attributes = dict(Attributes or {})
        custom_surface_mesh = dict(custom_surface_mesh or {})
        output_path = Path(output_mesh)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if margin_x == None:
            margin_x = margin
        if margin_y == None:
            margin_y = margin

        (
            substrate_thickness,
            airbox_height,
            margin_x,
            margin_y,
            volume_mesh_size,
            surface_mesh_size,
            refinement_radius,
        ) = (
            substrate_thickness * mesh_scale,
            airbox_height * mesh_scale,
            margin_x * mesh_scale,
            margin_y * mesh_scale,
            volume_mesh_size * mesh_scale,
            surface_mesh_size * mesh_scale,
            refinement_radius * mesh_scale,
        )
        custom_surface_mesh = {
            key: float(value) * mesh_scale
            for key, value in custom_surface_mesh.items()
        }

        finest_surface_mesh_size = surface_mesh_size
        if len(custom_surface_mesh) != 0:
            finest_surface_mesh_size = min(
                [surface_mesh_size] + list(custom_surface_mesh.values())
            )

        geom_tol = max(1e-12, geom_tol_factor * finest_surface_mesh_size)
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

        if "helper" in surfaces_df.columns:
            surfaces_df = surfaces_df[surfaces_df["helper"] == False]

        id_to_name = Mesh._qmetal_component_id_to_name(design)
        name_to_id = Mesh._qmetal_component_name_to_id(design)

        def polygons_from_geometry(geom: Any) -> list[Polygon]:
            if isinstance(geom, Polygon):
                return [geom]
            if isinstance(geom, MultiPolygon):
                return list(geom.geoms)
            return []

        PolyAttributeKey = str | tuple[int | str, str]

        def lookup_attr(
            component: Any, name: str
        ) -> tuple[int | None, PolyAttributeKey | None]:
            value, key = Mesh._lookup_qm_surface_key(
                Attributes, component, name, id_to_name
            )
            if value is None:
                return None, None
            return int(value), key

        def lookup_surface_mesh_size(component: Any, name: str) -> float:
            value, _ = Mesh._lookup_qm_surface_key(
                custom_surface_mesh, component, name, id_to_name
            )
            if value is None:
                return surface_mesh_size
            return float(value)

        attr_mesh_sizes: dict[int, float] = {}
        records: list[dict[str, Any]] = []
        for _, row in surfaces_df.iterrows():
            name = str(row["name"])
            component = row["component"]
            attr, key = lookup_attr(component, name)
            is_subtract = bool(row["subtract"])
            mesh_lc = lookup_surface_mesh_size(component, name)
            if attr != None:
                attr = int(attr)
                if attr in attr_mesh_sizes and attr_mesh_sizes[attr] != mesh_lc:
                    raise ValueError(
                        f"Conflicting custom_surface_mesh for attribute {attr}: "
                        f"{attr_mesh_sizes[attr]:g} vs {mesh_lc:g} on {name!r}."
                    )
                attr_mesh_sizes[attr] = mesh_lc

            for polygon in polygons_from_geometry(row["geometry"]):
                if mesh_scale != 1.0:
                    polygon = shapely_scale(
                        polygon,
                        xfact=mesh_scale,
                        yfact=mesh_scale,
                        origin=(0.0, 0.0),
                    )
                records.append(
                    {
                        "polygon": polygon,
                        "name": name,
                        "component": component,
                        "subtract": is_subtract,
                        "attribute": attr,
                        "key": key,
                        "mesh_lc": mesh_lc,
                    }
                )

        if not records:
            raise ValueError(
                "No surface geometry found in Quantum Metal design "
                "(poly + buffered path tables are empty)."
            )

        warnings: list[str] = []
        present_keys = {(record["component"], record["name"]) for record in records}
        present_names = {record["name"] for record in records}
        for key in Attributes:
            if not Mesh._qm_surface_key_matches_row(
                key,
                present_id_name_pairs=present_keys,
                present_names=present_names,
                name_to_id=name_to_id,
            ):
                warnings.append(f"Attributes key {key!r} matched no surface row")

        for key in custom_surface_mesh:
            if not Mesh._qm_surface_key_matches_row(
                key,
                present_id_name_pairs=present_keys,
                present_names=present_names,
                name_to_id=name_to_id,
                domain_keys=frozenset({"ground_plane", "far_field"}),
            ):
                warnings.append(
                    f"custom_surface_mesh key {key!r} matched no surface row"
                )

        tagged_records = [record for record in records if record["attribute"] is not None]

        bbox_geom = unary_union([record["polygon"] for record in records])
        xmin, ymin, xmax, ymax = bbox_geom.bounds
        xmin -= margin_x
        ymin -= margin_y
        xmax += margin_x
        ymax += margin_y
        dx = xmax - xmin
        dy = ymax - ymin
        z_substrate_bottom = -substrate_thickness

        simplify_stats: dict[str, int] | None = (
            {"polygon_edges": 0, "gmsh_curves": 0, "merged_runs": 0}
            if boundary_simplify is not None
            else None
        )

        def add_polygon_surface(polygon: Polygon, z: float, lc: float) -> int:
            return Mesh._gmsh_add_polygon_surface(
                gmsh,
                polygon,
                z,
                lc,
                boundary_simplify=boundary_simplify,
                scaled_surface_mesh_size=surface_mesh_size,
                finest_surface_mesh_size=finest_surface_mesh_size,
                mesh_scale=mesh_scale,
                simplify_stats=simplify_stats,
            )

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
            gmsh.model.add(
                "qiskit_metal_boundary_simplify_gmsh"
                if boundary_simplify is not None
                else "qiskit_metal_pure_gmsh"
            )

            substrate = gmsh.model.occ.addBox(
                xmin, ymin, z_substrate_bottom, dx, dy, substrate_thickness
            )
            airbox = gmsh.model.occ.addBox(xmin, ymin, 0.0, dx, dy, airbox_height)

            for record in records:
                record["surface_tag"] = add_polygon_surface(
                    record["polygon"], z=0.0, lc=record["mesh_lc"]
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
                label = Mesh._qmetal_physical_surface_name(
                    record["component"],
                    record["name"],
                    record["key"],
                    id_to_name,
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

            size_to_faces: dict[float, set[int]] = defaultdict(set)
            for attr, faces in attr_to_faces.items():
                size_to_faces[attr_mesh_sizes[attr]].update(faces)
            if gap_faces:
                size_to_faces[surface_mesh_size].update(gap_faces)

            if ground_plane_faces and "ground_plane" in custom_surface_mesh:
                size_to_faces[custom_surface_mesh["ground_plane"]].update(
                    ground_plane_faces
                )

            if farfield_faces and "far_field" in custom_surface_mesh:
                size_to_faces[custom_surface_mesh["far_field"]].update(farfield_faces)

            mesh_fields: list[int] = []
            for size_min, faces in size_to_faces.items():
                if not faces:
                    continue
                dist_field = gmsh.model.mesh.field.add("Distance")
                gmsh.model.mesh.field.setNumbers(
                    dist_field, "SurfacesList", sorted(faces)
                )
                gmsh.model.mesh.field.setNumber(dist_field, "Sampling", 100)

                thresh_field = gmsh.model.mesh.field.add("Threshold")
                gmsh.model.mesh.field.setNumber(thresh_field, "InField", dist_field)
                gmsh.model.mesh.field.setNumber(thresh_field, "SizeMin", size_min)
                gmsh.model.mesh.field.setNumber(
                    thresh_field, "SizeMax", volume_mesh_size
                )
                gmsh.model.mesh.field.setNumber(thresh_field, "DistMin", 0.0)
                gmsh.model.mesh.field.setNumber(
                    thresh_field, "DistMax", refinement_radius
                )
                mesh_fields.append(thresh_field)

            if len(mesh_fields) == 1:
                gmsh.model.mesh.field.setAsBackgroundMesh(mesh_fields[0])
            elif len(mesh_fields) > 1:
                min_field = gmsh.model.mesh.field.add("Min")
                gmsh.model.mesh.field.setNumbers(
                    min_field, "FieldsList", mesh_fields
                )
                gmsh.model.mesh.field.setAsBackgroundMesh(min_field)

            gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
            gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
            gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
            gmsh.option.setNumber(
                "Mesh.CharacteristicLengthMin", finest_surface_mesh_size
            )
            gmsh.option.setNumber("Mesh.CharacteristicLengthMax", volume_mesh_size)
            gmsh.option.setNumber("Mesh.ElementOrder", 1)
            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
            gmsh.option.setNumber("Mesh.Binary", 0)
            gmsh.option.setNumber("Mesh.SaveAll", 0)
            gmsh.option.setNumber("Mesh.Algorithm3D", 1)

            gmsh.model.mesh.generate(3)
            gmsh.write(str(output_path))

            if warnings:
                print("USER WARNING: " + "; ".join(warnings))

            if simplify_stats is not None:
                polygon_edges = simplify_stats.get("polygon_edges", 0)
                gmsh_curves = simplify_stats.get("gmsh_curves", 0)
                merged_runs = simplify_stats.get("merged_runs", 0)
                if polygon_edges > 0:
                    resolved = Mesh._resolve_boundary_simplify_settings(
                        boundary_simplify,
                        surface_mesh_size,
                        mesh_scale,
                        finest_surface_mesh_size=finest_surface_mesh_size,
                    )
                    print(
                        "boundary simplify: "
                        f"{polygon_edges} QM polygon edges -> "
                        f"{gmsh_curves} Gmsh curves "
                        f"({merged_runs} merged runs; "
                        f"short_edge={resolved.short_edge / mesh_scale:.4g} mm, "
                        f"cluster_span={resolved.cluster_span / mesh_scale:.4g} mm)"
                    )
                    if merged_runs == 0:
                        print(
                            "USER WARNING: boundary simplify merged 0 edge runs; "
                            "try lowering simplify_min_edges or raising "
                            "simplify_cluster_span / simplify_short_edge."
                        )

        finally:
            if owns_gmsh and gmsh.isInitialized():
                gmsh.finalize()

        mesh_attributes = Mesh.get_mesh_attributes(output_mesh)
        mesh_attributes = mesh_attributes.sort_values("ID")
        return mesh_attributes

    @staticmethod
    def mesh_Quantum_Metal_design_v2(
        design: Any,
        output_mesh: str | Path = "mesh_for_pyPalace.msh",
        *,
        Attributes: dict[str | tuple[int | str, str], int] | None = None,
        substrate_thickness: float = 0.5,
        airbox_height: float = 0.5,
        margin: float = 0.5,
        margin_x: float | None = None,
        margin_y: float | None = None,
        volume_mesh_size: float = 0.25,
        surface_mesh_size: float = 0.02,
        custom_surface_mesh: dict[str | tuple[int | str, str], float] | None = None,
        refinement_radius: float = 0.15,
        mesh_scale: float = 1000.0,
        ground_plane_attr: int | str = "auto",
        farfield_attr: int | str = "auto",
        substrate_attr: int | str = "auto",
        air_attr: int | str = "auto",
        geom_tol_factor: float = 0.01,
        boundary_simplify: "Mesh.BoundarySimplifySettings | None" = None,
        simplify_min_edges: int = 10,
        simplify_cluster_span: float | None = None,
        simplify_short_edge: float | None = None,
        simplify_smooth_angle_deg: float = 35.0,
        simplify_max_deviation: float | None = None,
    ):
        """Experimental QM mesher with automated short-edge boundary merging.

        Merges runs of many small polygon edges (circles, meander bends, rounded
        corners) into fewer Gmsh lines/splines before imprinting. Same Palace
        workflow as :meth:`mesh_Quantum_Metal_design`.

        Advanced users may pass a full :class:`BoundarySimplifySettings` object
        via ``boundary_simplify`` or override individual ``simplify_*`` kwargs.
        """
        if boundary_simplify is None:
            boundary_simplify = Mesh.BoundarySimplifySettings(
                min_edges=simplify_min_edges,
                cluster_span=simplify_cluster_span,
                short_edge=simplify_short_edge,
                smooth_angle_deg=simplify_smooth_angle_deg,
                max_deviation=simplify_max_deviation,
            )

        return Mesh.mesh_Quantum_Metal_design(
            design,
            output_mesh,
            Attributes=Attributes,
            substrate_thickness=substrate_thickness,
            airbox_height=airbox_height,
            margin=margin,
            margin_x=margin_x,
            margin_y=margin_y,
            volume_mesh_size=volume_mesh_size,
            surface_mesh_size=surface_mesh_size,
            custom_surface_mesh=custom_surface_mesh,
            refinement_radius=refinement_radius,
            mesh_scale=mesh_scale,
            ground_plane_attr=ground_plane_attr,
            farfield_attr=farfield_attr,
            substrate_attr=substrate_attr,
            air_attr=air_attr,
            geom_tol_factor=geom_tol_factor,
            boundary_simplify=boundary_simplify,
        )
