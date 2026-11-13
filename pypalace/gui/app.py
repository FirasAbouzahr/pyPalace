"""pyPalace GUI — Geometry (GDS / tag / ports / mesh) + Simulation.

Launch:
  pip install 'pypalace[gui]'
  pypalace-gui
  # or: python3 -m pypalace.gui
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from pypalace.gui.plots import build_tag_figure, parse_plotly_selection, summary_table
from pypalace.gui.state import GuiProject


st.set_page_config(
    page_title="pyPalace GUI",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="expanded",
)

_BC_OPTIONS = ["PEC", "Ground", "Terminal", "LumpedPort", "Absorbing", "(skip)"]
_TOOL_SELECT_METAL = "Select metals"
_TOOL_SELECT_GAP = "Select gaps"
_TOOL_DRAW_PORT = "Draw port"


def _project() -> GuiProject:
    if "project" not in st.session_state:
        st.session_state.project = GuiProject()
    return st.session_state.project


def _ensure_gui_deps() -> None:
    try:
        import plotly  # noqa: F401
    except ImportError:
        st.error(
            "Missing GUI deps. Install with:\n\n"
            "`pip install streamlit plotly` then `pip install -e . --no-deps`"
        )
        st.stop()


def _init_selection_state() -> None:
    st.session_state.setdefault("sel_polys", [])
    st.session_state.setdefault("sel_gaps", [])
    st.session_state.setdefault("port_corner1", None)
    st.session_state.setdefault("tool_mode", _TOOL_SELECT_METAL)
    st.session_state.setdefault("last_click_sig", None)


def _toggle_id(bucket: str, ident: int) -> None:
    cur = list(st.session_state.get(bucket, []))
    if ident in cur:
        cur = [x for x in cur if x != ident]
    else:
        cur.append(ident)
    st.session_state[bucket] = sorted(cur)


def _apply_canvas_clicks(event, tool: str) -> None:
    """Consume Streamlit plotly selection → toggle ids or place port corners."""
    selection = getattr(event, "selection", None)
    points = []
    if selection is not None:
        points = getattr(selection, "points", None) or []
        if not points and isinstance(selection, dict):
            points = selection.get("points", [])
    if not points:
        return

    # Deduplicate against identical re-runs of the same click payload
    sig = json.dumps(points, sort_keys=True, default=str)
    if sig == st.session_state.get("last_click_sig"):
        return
    st.session_state.last_click_sig = sig

    hits = parse_plotly_selection(event)
    if tool == _TOOL_DRAW_PORT:
        # Prefer raw click coordinates for port corners
        pt = points[0]
        if isinstance(pt, dict):
            x, y = float(pt.get("x")), float(pt.get("y"))
        else:
            x, y = float(pt.x), float(pt.y)
        c1 = st.session_state.port_corner1
        if c1 is None:
            st.session_state.port_corner1 = (x, y)
        else:
            st.session_state["pending_port_rect"] = (c1[0], c1[1], x, y)
            st.session_state.port_corner1 = None
        return

    for kind, ident in hits:
        if tool == _TOOL_SELECT_METAL and kind == "poly":
            _toggle_id("sel_polys", int(ident))
        elif tool == _TOOL_SELECT_GAP and kind == "gap":
            _toggle_id("sel_gaps", int(ident))


def page_geometry(project: GuiProject) -> None:
    st.header("Geometry · GDS → tag → ports → mesh")
    _init_selection_state()

    # ---- Load ----
    with st.expander("Import GDS", expanded=not bool(project.polygons)):
        up = st.file_uploader("GDS file", type=["gds", "GDS"])
        c1, c2, c3 = st.columns(3)
        with c1:
            mesh_scale = st.number_input(
                "mesh_scale",
                value=float(project.mesh_scale),
                help="1 = µm, 0.001 = nm, 1000 = mm. Length kwargs stay in µm.",
                format="%.6g",
            )
        with c2:
            layers_txt = st.text_input(
                "layers (optional)",
                value="",
                help='e.g. [(1,0),(2,0)] — empty = all layers',
            )
        with c3:
            cell_name = st.text_input("cell_name (optional)", value="")

        if up is not None and st.button("Load GDS", type="primary"):
            import ast

            tmp = Path(tempfile.mkdtemp()) / up.name
            tmp.write_bytes(up.getvalue())
            layers = None
            if layers_txt.strip():
                layers = ast.literal_eval(layers_txt.strip())
            try:
                project.load_gds(
                    tmp,
                    layers=layers,
                    cell_name=cell_name.strip() or None,
                )
                project.mesh_scale = float(mesh_scale)
                st.session_state.sel_polys = []
                st.session_state.sel_gaps = []
                st.session_state.port_corner1 = None
                st.session_state.last_click_sig = None
                st.success(
                    f"Loaded {len(project.polygons)} metals · "
                    f"{len(project.gap_pieces)} gaps from `{up.name}`"
                )
                st.rerun()
            except Exception as e:
                st.exception(e)

    if not project.polygons:
        st.info("Load a GDS to open the tagging canvas.")
        return

    st.caption(
        f"**{Path(project.gds_path).name}** · "
        f"{len(project.polygons)} metals · {len(project.gap_pieces)} gaps · "
        f"{len(project.ports)} ports · mesh_scale={project.mesh_scale}"
    )

    # ---- Tool + visibility ----
    tcol, v1, v2, v3 = st.columns([2, 1, 1, 1])
    with tcol:
        tool = st.radio(
            "Tool",
            [_TOOL_SELECT_METAL, _TOOL_SELECT_GAP, _TOOL_DRAW_PORT],
            horizontal=True,
            key="tool_mode",
        )
    with v1:
        show_metals = st.checkbox("Metals", value=True)
    with v2:
        show_gaps = st.checkbox("Gaps", value=True)
    with v3:
        show_ports = st.checkbox("Ports", value=True)

    left, right = st.columns([2.3, 1])

    with right:
        st.subheader("Selection")
        st.caption("Click the colored ● / ◆ markers on the canvas (or edit lists).")
        st.multiselect(
            "Metal ids (p*)",
            options=list(range(len(project.polygons))),
            key="sel_polys",
        )
        st.multiselect(
            "Gap ids (g*)",
            options=list(range(len(project.gap_pieces))),
            key="sel_gaps",
        )

        untagged_p = [
            i for i in range(len(project.polygons)) if i not in project.used_poly_ids()
        ]
        untagged_g = [
            i for i in range(len(project.gap_pieces)) if i not in project.used_gap_ids()
        ]
        st.caption(
            f"Untagged metals: {untagged_p[:24]}{'…' if len(untagged_p) > 24 else ''}  ·  "
            f"gaps: {untagged_g}"
        )

        if st.button("Clear selection"):
            st.session_state.sel_polys = []
            st.session_state.sel_gaps = []
            st.session_state.port_corner1 = None
            st.session_state.last_click_sig = None
            st.rerun()

        st.divider()
        st.subheader("Tag metal")
        m_name = st.text_input("Surface name", value="ground", key="m_name")
        m_attr = st.number_input("attr (0 = auto)", value=0, min_value=0, key="m_attr")
        m_union = st.checkbox(
            "union=True",
            value=True,
            help="Shapely-merge touching pieces at mesh time (fragmented grounds).",
        )
        if st.button("Tag metals", type="primary"):
            try:
                project.assign_surface(
                    m_name,
                    st.session_state.sel_polys,
                    attr=None if int(m_attr) == 0 else int(m_attr),
                    union=bool(m_union),
                )
                project.sim_settings.bc_map.setdefault(m_name.strip(), "PEC")
                st.session_state.sel_polys = []
                st.success(f"Tagged metal `{m_name}`")
                st.rerun()
            except Exception as e:
                st.error(str(e))

        st.subheader("Tag gap")
        g_name = st.text_input("Gap name", value="dgaps", key="g_name")
        g_attr = st.number_input("gap attr (0 = auto)", value=0, min_value=0, key="g_attr")
        if st.button("Tag gaps"):
            try:
                project.assign_gap(
                    g_name,
                    st.session_state.sel_gaps,
                    attr=None if int(g_attr) == 0 else int(g_attr),
                )
                project.sim_settings.bc_map.setdefault(g_name.strip(), "(skip)")
                st.session_state.sel_gaps = []
                st.success(f"Tagged gap `{g_name}`")
                st.rerun()
            except Exception as e:
                st.error(str(e))

        st.divider()
        st.subheader("Draw port")
        st.caption(
            "Select **Draw port**, click two opposite corners on the canvas, "
            "then confirm below."
        )
        p_name = st.text_input("Port name", value="port1", key="p_name")
        p_dir = st.selectbox(
            "Direction",
            ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
            index=2,
            key="p_dir",
        )
        p_R = st.number_input("R (Ω)", value=50.0, min_value=0.0, key="p_R")
        p_exc = st.checkbox("Excitation", value=False, key="p_exc")

        pending = st.session_state.get("pending_port_rect")
        if st.session_state.port_corner1 is not None:
            st.info(
                f"Corner 1 set at "
                f"({st.session_state.port_corner1[0]:.4g}, "
                f"{st.session_state.port_corner1[1]:.4g}) — click opposite corner."
            )
        if pending is not None:
            x0, y0, x1, y1 = pending
            st.write(
                f"Rectangle ready: "
                f"({x0:.4g},{y0:.4g}) → ({x1:.4g},{y1:.4g})"
            )
            if st.button("Add port", type="primary", key="add_port_btn"):
                try:
                    project.add_port(
                        p_name,
                        x0,
                        y0,
                        x1,
                        y1,
                        direction=p_dir,
                        R=float(p_R),
                        excitation=bool(p_exc),
                    )
                    st.session_state.pending_port_rect = None
                    st.success(f"Port `{p_name}` added")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if st.button("Discard rectangle"):
                st.session_state.pending_port_rect = None
                st.session_state.port_corner1 = None
                st.rerun()

        # Manual port entry fallback
        with st.expander("Or enter port coords manually"):
            mx0 = st.number_input("xmin", value=0.0, key="man_x0")
            my0 = st.number_input("ymin", value=0.0, key="man_y0")
            mx1 = st.number_input("xmax", value=10.0, key="man_x1")
            my1 = st.number_input("ymax", value=10.0, key="man_y1")
            if st.button("Add port from numbers"):
                try:
                    project.add_port(
                        p_name,
                        mx0,
                        my0,
                        mx1,
                        my1,
                        direction=p_dir,
                        R=float(p_R),
                        excitation=bool(p_exc),
                    )
                    st.success(f"Port `{p_name}` added")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        if project.ports:
            rm = st.selectbox("Remove port", options=["—"] + list(project.ports))
            if rm != "—" and st.button("Delete port"):
                project.remove_port(rm)
                st.rerun()

        if st.button("Clear all tags & ports"):
            project.surfaces.clear()
            project.gaps.clear()
            project.ports.clear()
            project.next_attr = 1
            project.sim_settings.bc_map.clear()
            st.rerun()

    with left:
        fig = build_tag_figure(
            project,
            highlight_polys=st.session_state.sel_polys,
            highlight_gaps=st.session_state.sel_gaps,
            show_metals=show_metals,
            show_gaps=show_gaps,
            show_ports=show_ports,
            port_corner=st.session_state.port_corner1,
        )
        event = st.plotly_chart(
            fig,
            use_container_width=True,
            key="gds_canvas",
            on_select="rerun",
            selection_mode="points",
            config={"scrollZoom": True, "displaylogo": False},
        )
        _apply_canvas_clicks(event, tool)

    st.subheader("Current tags")
    df = summary_table(project)
    if df.empty:
        st.caption("No tags yet — click markers, then Tag metals / Tag gaps.")
    else:
        st.dataframe(df, use_container_width=True)

    # ---- Mesh ----
    st.divider()
    st.subheader("Mesh")
    ms = project.mesh_settings
    m1, m2, m3 = st.columns(3)
    with m1:
        ms.substrate_thickness = st.number_input(
            "substrate_thickness (µm)", value=float(ms.substrate_thickness)
        )
        ms.airbox_height = st.number_input(
            "airbox_height (µm)", value=float(ms.airbox_height)
        )
        ms.margin = st.number_input("margin (µm)", value=float(ms.margin))
    with m2:
        ms.volume_mesh_size = st.number_input(
            "volume_mesh_size (µm)", value=float(ms.volume_mesh_size)
        )
        ms.surface_mesh_size = st.number_input(
            "surface_mesh_size (µm)", value=float(ms.surface_mesh_size)
        )
        ms.refinement_radius = st.number_input(
            "refinement_radius (µm)", value=float(ms.refinement_radius)
        )
    with m3:
        ms.output_mesh = st.text_input("output_mesh", value=ms.output_mesh)
        csm_txt = st.text_input(
            "custom_surface_mesh JSON",
            value=json.dumps(ms.custom_surface_mesh) if ms.custom_surface_mesh else "{}",
            help='e.g. {"dgaps": 1, "port1": 2}',
        )
        try:
            ms.custom_surface_mesh = json.loads(csm_txt) if csm_txt.strip() else {}
        except json.JSONDecodeError:
            st.warning("custom_surface_mesh must be valid JSON")

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Run mesh", type="primary"):
            try:
                with st.spinner("Meshing…"):
                    table = project.run_mesh()
                st.success(f"Wrote `{project.last_mesh_path}`")
                st.dataframe(table, use_container_width=True)
            except Exception as e:
                st.exception(e)
    with b2:
        data = project.export_dict()
        st.download_button(
            "Download maps JSON",
            data=json.dumps(data, indent=2),
            file_name="pypalace_gds_maps.json",
            mime="application/json",
        )
    with b3:
        tmp = Path(tempfile.mkdtemp()) / "mesh_from_gui.py"
        project.export_python(tmp)
        st.download_button(
            "Download mesh script (.py)",
            data=tmp.read_text(),
            file_name="mesh_from_gui.py",
            mime="text/x-python",
        )

    if project.last_attr_table is not None and project.last_mesh_path:
        st.caption(f"Last mesh: `{project.last_mesh_path}`")
        with st.expander("Attribute table"):
            st.dataframe(project.last_attr_table, use_container_width=True)


def page_simulation(project: GuiProject) -> None:
    st.header("Simulation · Palace setup & run")
    if not project.surfaces and not project.ports:
        st.warning("Tag metals / draw ports on the Geometry tab first.")
        return

    ss = project.sim_settings
    attrs = project.named_attrs()

    st.subheader("Problem")
    c1, c2, c3 = st.columns(3)
    with c1:
        ss.problem_type = st.selectbox(
            "Problem type",
            ["Electrostatic", "Eigenmode", "Driven", "Magnetostatic"],
            index=["Electrostatic", "Eigenmode", "Driven", "Magnetostatic"].index(
                ss.problem_type
            )
            if ss.problem_type
            in ("Electrostatic", "Eigenmode", "Driven", "Magnetostatic")
            else 0,
        )
        ss.order = int(st.number_input("Solver Order", value=int(ss.order), min_value=1, max_value=5))
    with c2:
        ss.output_dir = st.text_input("Output directory", value=ss.output_dir)
        ss.config_path = st.text_input("Config JSON path", value=ss.config_path)
    with c3:
        ss.L0 = float(
            st.number_input("Model L0 (m)", value=float(ss.L0), format="%.3e")
        )
        mesh_hint = project.last_mesh_path or project.mesh_settings.output_mesh
        st.text_input("Mesh file", value=mesh_hint, disabled=True)

    st.subheader("Materials")
    m1, m2 = st.columns(2)
    with m1:
        ss.substrate_eps = st.number_input(
            "Substrate εr", value=float(ss.substrate_eps)
        )
    with m2:
        ss.substrate_loss_tan = float(
            st.number_input(
                "Substrate LossTan",
                value=float(ss.substrate_loss_tan),
                format="%.3e",
            )
        )

    st.subheader("Boundary conditions")
    st.caption(
        "Dropdowns for every tagged metal, gap, and drawn port "
        "(plus substrate/air/far_field after a mesh run)."
    )
    names = list(dict.fromkeys([*project.surfaces, *project.gaps, *project.ports, *attrs]))
    # Prefer human tags first, then auto volumes
    auto = [n for n in ("substrate", "air", "far_field") if n in attrs]
    ordered = [n for n in names if n not in auto] + auto

    for n in ordered:
        a = attrs.get(n)
        default = ss.bc_map.get(n)
        if default is None:
            if n in project.ports:
                default = "LumpedPort"
            elif n == "far_field":
                default = "Absorbing"
            elif n in ("substrate", "air"):
                default = "(skip)"
            else:
                default = "PEC"
        idx = _BC_OPTIONS.index(default) if default in _BC_OPTIONS else 0
        label = f"`{n}`" + (f"  (attr {a})" if a is not None else "  (attr pending mesh)")
        ss.bc_map[n] = st.selectbox(label, _BC_OPTIONS, index=idx, key=f"bc_{n}")

        if ss.bc_map[n] == "LumpedPort" and n in project.ports:
            port = project.ports[n]
            pc1, pc2, pc3 = st.columns(3)
            with pc1:
                port.direction = st.selectbox(
                    f"{n} direction",
                    ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
                    index=["+X", "-X", "+Y", "-Y", "+Z", "-Z"].index(port.direction)
                    if port.direction in ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
                    else 2,
                    key=f"pdir_{n}",
                )
            with pc2:
                port.R = float(st.number_input(f"{n} R (Ω)", value=float(port.R), key=f"pR_{n}"))
            with pc3:
                port.excitation = st.checkbox(
                    f"{n} Excitation", value=bool(port.excitation), key=f"pexc_{n}"
                )

    st.subheader("Run")
    r1, r2 = st.columns(2)
    with r1:
        ss.path_to_palace = st.text_input(
            "Path to palace executable",
            value=ss.path_to_palace,
            help="Leave blank to try get_palace_executable().",
        )
    with r2:
        ss.n_mpi = int(st.number_input("MPI processes", value=int(ss.n_mpi), min_value=1))

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Build & save config JSON", type="primary"):
            try:
                cfg = project.build_palace_config()
                Path(ss.config_path).parent.mkdir(parents=True, exist_ok=True)
                cfg.save_config(check_validity=True)
                st.success(f"Wrote `{ss.config_path}`")
                st.json(cfg.config)
            except Exception as e:
                st.exception(e)
    with b2:
        if st.button("Preview config (no save)"):
            try:
                cfg = project.build_palace_config()
                st.json(cfg.config)
            except Exception as e:
                st.exception(e)
    with b3:
        if st.button("Run Palace"):
            try:
                from pypalace.simulation import Simulation

                cfg = project.build_palace_config()
                Path(ss.config_path).parent.mkdir(parents=True, exist_ok=True)
                cfg.save_config(check_validity=True)
                palace = ss.path_to_palace.strip()
                if not palace:
                    from pypalace.palace_env import get_palace_executable

                    palace = get_palace_executable()
                sim = Simulation(cfg, palace)
                with st.spinner(f"Running Palace (n={ss.n_mpi})…"):
                    sim.run(n=ss.n_mpi)
                st.success("Palace finished.")
            except Exception as e:
                st.exception(e)

    st.caption(
        "Tip: mesh on the Geometry tab first so substrate / air / far_field attrs "
        "are known. Drawn ports are meshed as extra metal faces and wired as LumpedPorts."
    )


def main() -> None:
    _ensure_gui_deps()
    st.title("pyPalace")
    st.caption(
        "Geometry: import · click-tag · draw ports · mesh.  "
        "Simulation: Palace BCs · config · run."
    )
    project = _project()
    tab1, tab2 = st.tabs(["Geometry", "Simulation"])
    with tab1:
        page_geometry(project)
    with tab2:
        page_simulation(project)


main()
