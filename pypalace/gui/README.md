# pyPalace GUI

Optional Streamlit app:

1. **Geometry** — import GDS, click-tag metals (`p*`) & gaps (`g*`), draw lumped-port rectangles, run mesh, export maps / script
2. **Simulation** — Palace problem / materials / BC dropdowns, write config JSON, optionally run

## Install & launch

```bash
pip install 'pypalace[gui]'
pypalace-gui
# or: python3 -m pypalace.gui
```

Opens http://localhost:8501.

### macOS tip (CadQuery / `nlopt` pip fights)

Tagging only needs `gdstk` + Streamlit. If `pip install -e '.[gui]'` dies on `nlopt`:

```bash
pip install streamlit plotly
pip install -e . --no-deps
python3 -m pypalace.gui
```

Meshing still needs MeshWell (conda recommended for CadQuery).

## Geometry tab tips

- Click the colored **●** (metal) / **◆** (gap) markers — labels match `inspect_gds` (leader lines).
- Tool **Draw port**: click two opposite corners, then **Add port**.
- Ports are meshed as extra metal faces and default to `LumpedPort` on the Simulation tab.
