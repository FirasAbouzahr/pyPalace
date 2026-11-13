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
python -m pypalace.gui
```

Opens a local Streamlit page in your browser (default http://localhost:8501).
