"""pyPalace GDS tagger GUI (Streamlit).

Launch:
  pip install 'pypalace[gui]'
  pypalace-gui
  # or: python -m pypalace.gui
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from pypalace.gui.plots import build_tag_figure, summary_table
from pypalace.gui.state import GuiProject


st.set_page_config(
    page_title="pyPalace GUI",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _project() -> GuiProject:
    if "project" not in st.session_state:
        st.session_state.project = GuiProject()
    return st.session_state.project


def _ensure_gui_deps() -> None:
    try:
        import plotly  # noqa: F401
    except ImportError as e:
        st.error(
            "Missing GUI deps. Install with:\n\n"
            "`pip install 'pypalace[gui]'` or `pip install -e '.[gui]'`"
        )
        st.stop()


def page_import(project: GuiProject) -> None:
    st.header("1 · Import GDS")
    st.caption("GDS-only v1. Metals and dielectric gaps share one tagging canvas.")

    up = st.file_uploader("GDS file", type=["gds", "GDS"])
    col1, col2, col3 = st.columns(3)
    with col1:
        mesh_scale = st.number_input(
            "mesh_scale",
            value=float(project.mesh_scale),
            help="1 = µm GDS, 0.001 = nm GDS, 1000 = mm GDS. Length kwargs stay in µm.",
            format="%.6g",
        )
    with col2:
        layers_txt = st.text_input(
            "layers (optional)",
            value="",
            help='e.g. [(1,0),(2,0)] — empty = all layers',
        )
    with col3:
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
            st.success(
                f"Loaded {len(project.polygons)} metal polys, "
                f"{len(project.gap_pieces)} gap pieces from `{up.name}`"
            )
        except Exception as e:
            st.exception(e)

    if project.polygons:
        st.info(
            f"**{Path(project.gds_path).name}** · "
            f"{len(project.polygons)} metals · {len(project.gap_pieces)} gaps · "
            f"mesh_scale={project.mesh_scale}"
        )


def page_tag(project: GuiProject) -> None:
    st.header("2 · Tag metals & gaps")
    if not project.polygons:
        st.warning("Import a GDS first.")
        return

    show_m, show_g = st.columns(2)
    with show_m:
        show_metals = st.checkbox("Show metals", value=True)
    with show_g:
        show_gaps = st.checkbox("Show gaps", value=True)

    left, right = st.columns([2.2, 1])

    with right:
        st.subheader("Selection")
        untagged_p = [
            i for i in range(len(project.polygons)) if i not in project.used_poly_ids()
        ]
        untagged_g = [
            i for i in range(len(project.gap_pieces)) if i not in project.used_gap_ids()
        ]
        sel_polys = st.multiselect(
            "Metal poly ids (p*)",
            options=list(range(len(project.polygons))),
            default=[],
            help="Fragmented ground pieces → select many → one name + Merge/union",
        )
        sel_gaps = st.multiselect(
            "Gap ids (g*)",
            options=list(range(len(project.gap_pieces))),
            default=[],
        )
        st.caption(
            f"Untagged metals: {untagged_p[:20]}{'…' if len(untagged_p) > 20 else ''} · "
            f"Untagged gaps: {untagged_g}"
        )

        st.subheader("Assign metal")
        m_name = st.text_input("Surface name", value="ground", key="m_name")
        m_attr = st.number_input("attr (blank = auto)", value=0, min_value=0, key="m_attr")
        m_union = st.checkbox(
            "union=True (Shapely-merge pieces at mesh time)",
            value=True,
            help="Recommended for fragmented ground banks.",
        )
        if st.button("Tag metals", type="primary"):
            try:
                project.assign_surface(
                    m_name,
                    sel_polys,
                    attr=None if int(m_attr) == 0 else int(m_attr),
                    union=bool(m_union),
                )
                st.success(f"Tagged metal `{m_name}` ← {sel_polys}")
            except Exception as e:
                st.error(str(e))

        st.subheader("Assign gap")
        g_name = st.text_input("Gap name", value="dgaps", key="g_name")
        g_attr = st.number_input("gap attr (0 = auto)", value=0, min_value=0, key="g_attr")
        if st.button("Tag gaps"):
            try:
                project.assign_gap(
                    g_name,
                    sel_gaps,
                    attr=None if int(g_attr) == 0 else int(g_attr),
                )
                st.success(f"Tagged gap `{g_name}` ← {sel_gaps}")
            except Exception as e:
                st.error(str(e))

        if st.button("Clear all tags"):
            project.surfaces.clear()
            project.gaps.clear()
            project.next_attr = 1
            st.info("Cleared tags.")

    with left:
        fig = build_tag_figure(
            project,
            highlight_polys=sel_polys,
            highlight_gaps=sel_gaps,
            show_metals=show_metals,
            show_gaps=show_gaps,
        )
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

    st.subheader("Current tags")
    df = summary_table(project)
    if df.empty:
        st.caption("No tags yet.")
    else:
        st.dataframe(df, use_container_width=True)


def page_export(project: GuiProject) -> None:
    st.header("3 · Export maps + script")
    if not project.surfaces and not project.gaps:
        st.warning("Tag at least one metal or gap first.")
        return

    data = project.export_dict()
    st.subheader("surface_map / gap_map preview")
    st.json(data)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download maps JSON",
            data=json.dumps(data, indent=2),
            file_name="pypalace_gds_maps.json",
            mime="application/json",
        )
    with col2:
        py_txt = _python_script_text(project)
        st.download_button(
            "Download mesh script (.py)",
            data=py_txt,
            file_name="mesh_from_gui.py",
            mime="text/x-python",
        )

    st.subheader("Mesh / Palace (next)")
    st.caption(
        "v1 exports maps + a runnable `mesh_gds` script. "
        "Mesh-run and Palace BC dropdowns land in a follow-up on this branch."
    )
    with st.expander("Palace BC sketch (preview)"):
        names = list(project.surfaces) + list(project.gaps)
        if not names:
            st.write("No tagged surfaces yet.")
        else:
            for n in names:
                bc = st.selectbox(
                    f"BC for `{n}`",
                    options=["PEC", "Ground", "Terminal", "LumpedPort", "Absorbing", "(skip)"],
                    key=f"bc_{n}",
                )
                st.caption(f"{n} → {bc}")


def _python_script_text(project: GuiProject) -> str:
    tmp = Path(tempfile.mkdtemp()) / "mesh_from_gui.py"
    project.export_python(tmp)
    return tmp.read_text()


def main() -> None:
    _ensure_gui_deps()
    st.title("pyPalace · GDS tagger")
    st.caption(
        "Import → tag metals & gaps on one canvas → export JSON + `.py`. "
        "Optional install: `pip install 'pypalace[gui]'` → `pypalace-gui`"
    )

    project = _project()
    tab1, tab2, tab3 = st.tabs(["Import GDS", "Tag surfaces", "Export"])
    with tab1:
        page_import(project)
    with tab2:
        page_tag(project)
    with tab3:
        page_export(project)


main()
