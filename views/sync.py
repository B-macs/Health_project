"""Voice Training route backed by the Voxplot submodule."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import streamlit as st


_VOXPLOT_ROOT = Path(__file__).resolve().parents[1] / "voice_training" / "voxplot"
_VOXPLOT_APP = _VOXPLOT_ROOT / "app.py"
_VOXPLOT_MODULE_NAME = "_health_embedded_voxplot"
_VOXPLOT_REPO_URL = "https://github.com/B-macs/health-voice-training.git"
_VOXPLOT_TOP_LEVEL_PACKAGES = {"analysis", "storage", "ui", "config"}
"""Voxplot's own top-level module names, imported into this process by its
app.py. They must be purged alongside the entry point when reloading a
changed checkout, or the re-import quietly binds the previous versions."""

# Voxplot's own app.py already defaults this to "voxplot_supabase" (see
# storage/supabase.py's SECRETS_KEY), matching Health's secrets.toml
# section below -- set explicitly anyway so this integration point doesn't
# silently depend on Voxplot's current default staying what it is today.
# Must be set before module.render() below makes its first storage call,
# since app.py's _record_store() reads it on first use only.
os.environ.setdefault("VOXPLOT_SUPABASE_SECRETS_KEY", "voxplot_supabase")


def _git(*args: str, cwd: Path | None = None, timeout: int = 90) -> str:
    """Run one git command, returning stdout. Raises on failure -- callers
    decide what a failure means."""
    result = subprocess.run(
        ["git", *args], cwd=str(cwd) if cwd else None,
        check=True, capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout.strip()


def _pinned_voxplot_sha() -> str | None:
    """The Voxplot commit this repo's submodule actually points at.

    Streamlit Community Cloud clones Health but never runs
    `git submodule update --init`, so the working tree has no Voxplot files
    -- but the *gitlink* is still in Health's tree, and `git ls-tree` reads
    it straight out of the commit. That is what makes the pin recoverable in
    a deployment that has no submodule checkout at all.

    Returns None when it can't be read (not a git repo, no git binary), in
    which case the caller falls back to tracking the default branch."""
    try:
        entry = _git("ls-tree", "HEAD", "voice_training/voxplot",
                     cwd=Path(__file__).resolve().parents[1], timeout=15)
    except Exception:
        return None
    # "160000 commit <sha>\tvoice_training/voxplot"
    parts = entry.split()
    return parts[2] if len(parts) >= 3 and parts[1] == "commit" else None


def _current_voxplot_sha() -> str | None:
    try:
        return _git("rev-parse", "HEAD", cwd=_VOXPLOT_ROOT, timeout=15)
    except Exception:
        return None


def _self_heal_voxplot_checkout() -> None:
    """Put the pinned Voxplot commit on disk, whatever state we start from.

    Streamlit Community Cloud clones this repo without initializing git
    submodules, so voice_training/voxplot/ arrives empty on every deploy even
    though it's fully populated locally.

    An earlier version cloned `--depth 1` and stopped there, which had two
    faults worth naming because both were silent. It fetched whatever the
    default branch happened to be at container start, so the submodule pin
    had no effect on what actually ran -- the deployed app was reproducible
    only by luck. And it returned early whenever the directory was non-empty,
    so a container holding an older clone kept serving it indefinitely, with
    a pin bump doing nothing to dislodge it.

    So: resolve the pin from Health's own git tree, clone if missing, and
    check that exact commit out -- correcting a checkout that is merely at
    the wrong revision instead of leaving it alone. Falls back to tracking
    the default branch only when the pin genuinely can't be read, which is
    better than refusing to render at all.

    Swallows its own errors; render() re-checks _VOXPLOT_APP afterward and
    shows the manual-init warning if this didn't work (no network, no git)."""
    pinned = _pinned_voxplot_sha()

    if _VOXPLOT_ROOT.exists() and any(_VOXPLOT_ROOT.iterdir()):
        # Already populated. Only touch it if it's at the wrong commit --
        # and only when we know which commit is right.
        if pinned is None or _current_voxplot_sha() == pinned:
            return
        with st.spinner("Updating Voice Training..."):
            try:
                _git("fetch", "--depth", "1", "origin", pinned, cwd=_VOXPLOT_ROOT)
                _git("checkout", "--force", pinned, cwd=_VOXPLOT_ROOT)
            except Exception:
                # A shallow clone can't always reach an arbitrary commit.
                # Re-clone from scratch rather than run mismatched code.
                shutil.rmtree(_VOXPLOT_ROOT, ignore_errors=True)
            else:
                return

    with st.spinner("Setting up Voice Training..."):
        _VOXPLOT_ROOT.parent.mkdir(parents=True, exist_ok=True)
        if pinned is None:
            _git("clone", "--depth", "1", _VOXPLOT_REPO_URL, str(_VOXPLOT_ROOT))
            return
        # Full clone: --depth 1 only reaches the branch tip, and the pin is
        # frequently an older commit than that.
        _git("clone", _VOXPLOT_REPO_URL, str(_VOXPLOT_ROOT))
        _git("checkout", "--force", pinned, cwd=_VOXPLOT_ROOT)


_LOADED_SHA_ATTR = "_health_loaded_from_sha"


def _load_voxplot(expected_sha: str | None = None) -> ModuleType:
    """Load the submodule entry point under a distinct name from Health's app.py.

    The cached module is reused only while it came from the commit now on
    disk. Python caches by module name, so once Voxplot has been imported the
    process keeps serving it regardless of the files underneath -- which meant
    a checkout corrected by _self_heal_voxplot_checkout() had no effect until
    the container itself restarted. Stamping the module with the SHA it was
    built from makes a changed checkout force a genuine re-import."""
    loaded = sys.modules.get(_VOXPLOT_MODULE_NAME)
    if loaded is not None:
        if expected_sha is None or getattr(loaded, _LOADED_SHA_ATTR, None) == expected_sha:
            return loaded
        # Stale: drop it so the code below re-executes the new files. Its own
        # submodules are namespaced under Voxplot's package names, so purge
        # those too or the re-import silently reuses the old ones.
        sys.modules.pop(_VOXPLOT_MODULE_NAME, None)
        for name in [n for n in sys.modules if n.split(".")[0] in _VOXPLOT_TOP_LEVEL_PACKAGES]:
            sys.modules.pop(name, None)

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
    setattr(module, _LOADED_SHA_ATTR, expected_sha)
    return module


def render() -> None:
    """Render Voxplot within Health while retaining its standalone entry point."""
    # Runs even when app.py is already present: the checkout may exist but sit
    # at the wrong commit, which is precisely the case the old "return early if
    # non-empty" guard could never correct.
    try:
        _self_heal_voxplot_checkout()
    except Exception:
        pass  # fall through to the is_file() check below

    if not _VOXPLOT_APP.is_file():
        st.warning("Voice Training is not available because the Voxplot submodule is missing.")
        st.code("git submodule update --init --recursive")
        return

    original_cwd = Path.cwd()
    try:
        module = _load_voxplot(_current_voxplot_sha())
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
