"""Entry point: ``python -m pypalace.gui`` or ``pypalace-gui``."""

from __future__ import annotations

import sys
from pathlib import Path


def main(port: int | None = None) -> None:
    try:
        from streamlit.web import cli as stcli
    except ImportError as e:
        raise SystemExit(
            "The pyPalace GUI requires the optional [gui] extra.\n"
            "  pip install 'pypalace[gui]'\n"
            "or from a clone: pip install -e '.[gui]'"
        ) from e

    app = Path(__file__).resolve().parent / "app.py"
    argv = ["streamlit", "run", str(app), "--server.headless=true"]
    if port is not None:
        argv.append(f"--server.port={int(port)}")
    # Forward extra CLI args after -- if present.
    if "--" in sys.argv:
        argv.extend(sys.argv[sys.argv.index("--") + 1 :])
    sys.argv = argv
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
