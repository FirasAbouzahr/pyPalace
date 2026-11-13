# pyPalace GUI (GDS tagger)

Optional Streamlit app for GDS-only workflows:

1. **Import GDS** — layers / `mesh_scale`
2. **Tag metals & gaps** — same canvas (`p*` metals + `g*` gaps); assign names/attrs; set `union=True` for fragmented grounds
3. **Export** — SurfaceMap / GapMap JSON + runnable `mesh_gds` `.py` script

Palace BC dropdowns / in-app meshing come next on this branch.

## Install & launch

```bash
pip install 'pypalace[gui]'
pypalace-gui
```

From a clone:

```bash
pip install -e '.[gui]'
python3 -m pypalace.gui
```

Opens a local Streamlit page in your browser (default http://localhost:8501).

### macOS tip (CadQuery / `nlopt` pip fights)

Tagging in the GUI only needs `gdstk` + Streamlit — not a full MeshWell/CadQuery stack.
If `pip install -e '.[gui]'` dies while building `nlopt`, skip the dependency resolve:

```bash
cd ~/pyPalace
git pull origin cursor/gui-gds-tagger-92d0

pip install streamlit plotly
pip install -e . --no-deps
python3 -m pypalace.gui
```

For actual meshing later, install MeshWell/CadQuery via **conda** (recommended) or pin wheels before pip:

```bash
pip install 'nlopt>=2.9' 'cadquery==2.8.0' meshwell
```
