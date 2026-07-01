import sys
from pathlib import Path


def get_bundle_path() -> Path:
    """Get base path, handles both frozen (PyInstaller) and source runs."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in a PyInstaller bundle
        return Path(sys._MEIPASS)
    else:
        # Running from source
        return Path(__file__).parent.parent.parent


def get_data_path(relative_path: str) -> Path:
    """Get path to data file, works for both source and bundled."""
    return get_bundle_path() / relative_path
