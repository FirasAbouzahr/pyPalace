"""Optional GDS tagging / Palace setup GUI (``pip install pypalace[gui]``)."""

from __future__ import annotations


def launch(*, port: int | None = None) -> None:
    """Launch the Streamlit GUI (``python -m pypalace.gui`` / ``pypalace-gui``)."""
    from .__main__ import main

    main(port=port)
