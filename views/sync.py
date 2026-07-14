"""Voice Training route backed by the Voxplot submodule."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import streamlit as st


_VOXPLOT_ROOT = Path(__file__).resolve().parents[1] / "voice_training" / "voxplot"
_VOXPLOT_APP = _VOXPLOT_ROOT / "app.py"
_VOXPLOT_MODULE_NAME = "_health_embedded_voxplot"


def _load_voxplot() -> ModuleType:
    """Load the submodule entry point under a distinct name from Health's app.py."""
    loaded = sys.modules.get(_VOXPLOT_MODULE_NAME)
    if loaded is not None:
        return loaded

    source_root = str(_VOXPLOT_ROOT)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)

    spec = importlib.util.spec_from_file_location(_VOXPLOT_MODULE_NAME, _VOXPLOT_APP)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load the Voxplot entry point.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_VOXPLOT_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_VOXPLOT_MODULE_NAME, None)
        raise
    return module


def render() -> None:
    """Render Voxplot within Health while retaining its standalone entry point."""
    if not _VOXPLOT_APP.is_file():
        st.warning("Voice Training is not available because the Voxplot submodule is missing.")
        st.code("git submodule update --init --recursive")
        return

    original_cwd = Path.cwd()
    try:
        module = _load_voxplot()
        os.chdir(_VOXPLOT_ROOT)
        module.render(embedded=True)
    except ModuleNotFoundError as exc:
        st.error(f"Voice Training dependency unavailable: {exc.name}")
        st.caption("Install the Health app requirements to enable Voxplot audio analysis.")
    except Exception as exc:
        st.error("Voice Training could not start.")
        st.exception(exc)
    finally:
        os.chdir(original_cwd)
