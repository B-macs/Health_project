"""Which process runs the background writes (rebuild rule 2; Phase 2,
milestone 4, 2026-10-19).

Until the switch-over (Phase 9) the Streamlit app runs the Oura and Garmin
syncs and the automatic writes (the failed-week rule, and the readiness shift's
and the missed-session carry's records that move nothing); after it, only the
engine does. Oura spends its refresh token at every refresh, so two processes
refreshing break the login, and two processes applying the failed-week rule
can judge one week twice.

The setting lives in the store's config table under CONFIG_KEY, read from the
store ITSELF (Repository.get_config_value_live), because the other process
can change it after this one built its local copy:

    "streamlit"  the Streamlit app writes; the engine refuses.
    "engine"     the engine writes; the Streamlit app refuses.
    absent       "streamlit" — the app as it runs today.
    anything else, or a failed read: NOBODY writes. A background write made
                 without permission is the failure this exists to stop, so
                 an unknown answer is never read as a yes.

Each process names itself in Config.background_process ("streamlit" in
repo.py, "engine" in the API's settings); a process that names nothing (a
script, a test) is not checked.
"""

from __future__ import annotations

CONFIG_KEY = "background_writer"
STREAMLIT = "streamlit"
ENGINE = "engine"
WRITERS = (STREAMLIT, ENGINE)
#: The writer when the setting was never stored: the app as it runs today.
DEFAULT = STREAMLIT


class NotTheWriterError(RuntimeError):
    """This process is not the background writer, so it must not write."""


def current(repo) -> str | None:
    """The writer the store names: the setting, DEFAULT when absent, None
    when the store cannot be read or the setting names no writer."""
    try:
        raw = repo.get_config_value_live(CONFIG_KEY)
    except Exception:
        return None
    if raw is None or str(raw).strip() == "":
        return DEFAULT
    value = str(raw).strip().lower()
    return value if value in WRITERS else None


def may_write(repo, process: str) -> bool:
    """Whether `process` is the background writer now."""
    return current(repo) == process


def require(repo, process: str) -> None:
    """NotTheWriterError unless `process` is the background writer."""
    writer = current(repo)
    if writer != process:
        raise NotTheWriterError(
            f"the background writer is {writer or 'unknown'}, not {process}")
