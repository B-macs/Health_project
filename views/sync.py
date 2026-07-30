"""Voice Training route backed by the Voxplot submodule."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import streamlit as st


_VOXPLOT_ROOT = Path(__file__).resolve().parents[1] / "voice_training" / "voxplot"
_VOXPLOT_APP = _VOXPLOT_ROOT / "app.py"
_VOXPLOT_MODULE_NAME = "_health_embedded_voxplot"
_VOXPLOT_REPO_URL = "https://github.com/B-macs/health-voice-training.git"

# Voxplot's own app.py already defaults this to "voxplot_supabase" (see
# storage/supabase.py's SECRETS_KEY), matching Health's secrets.toml
# section below -- set explicitly anyway so this integration point doesn't
# silently depend on Voxplot's current default staying what it is today.
# Must be set before module.render() below makes its first storage call,
# since app.py's _record_store() reads it on first use only.
os.environ.setdefault("VOXPLOT_SUPABASE_SECRETS_KEY", "voxplot_supabase")


def _self_heal_voxplot_checkout() -> None:
    """Streamlit Community Cloud clones this repo without initializing git
    submodules (`git submodule update --init` never runs there), so
    voice_training/voxplot/ arrives as an empty placeholder directory on
    every deploy even though it's fully populated locally. Shallow-clone
    the public Voxplot repo straight into that path the first time it's
    found empty -- a few seconds of one-time cost per container start.
    Swallows its own errors; render() re-checks _VOXPLOT_APP afterward and
    falls back to the manual-init warning if this didn't work (e.g. no
    outbound network, no git binary)."""
    if _VOXPLOT_ROOT.exists() and any(_VOXPLOT_ROOT.iterdir()):
        return  # non-empty but missing app.py -- something else is wrong; don't clobber it
    with st.spinner("Setting up Voice Training for the first time..."):
        subprocess.run(
            ["git", "clone", "--depth", "1", _VOXPLOT_REPO_URL, str(_VOXPLOT_ROOT)],
            check=True, capture_output=True, text=True, timeout=60,
        )


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
        try:
            _self_heal_voxplot_checkout()
        except Exception:
            pass  # fall through to the is_file() re-check below

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
