"""
Asserts no @st.cache_data / @st.cache_resource function calls an st element
that renders outside the MAIN or SIDEBAR container — today st.toast and
st.chat_input.

WHY THIS IS A TEST AND NOT A COMMENT. A cache-decorated function RECORDS the
st elements it emits and REPLAYS them on every later cache hit. The replay
(streamlit/runtime/caching/cached_message_replay.py::replay_cached_messages)
seeds its DeltaGenerator map with exactly two entries, `result.main_id` and
`result.sidebar_id`. st.toast renders on the EVENT container and st.chat_input
on BOTTOM (streamlit/delta_generator_singletons.py builds _main_dg,
_sidebar_dg, _event_dg and _bottom_dg), so neither id is in that map, the
lookup raises KeyError, and Streamlit re-raises it as CacheReplayClosureError.

The failure that produced this test: `repo.get_repository()` toasted
"Rebuilt the local read cache from Supabase" from inside @st.cache_resource.
That call site only runs in cache mode after a redeploy has wiped the
ephemeral disk — i.e. ONLY on the hosted deploy, never in a local checkout —
and it takes down app.py's first line of work on the second script run and
every one after, so the first paint looks healthy and the first navigation
dies. Nothing local reproduces it and no other test would have caught it.

This is NOT a general ban on drawing from a cached function: ordinary
elements (st.warning, st.write, st.markdown) replay correctly, which is the
whole point of the replay machinery.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# st function name -> the root container it renders on. Neither is seeded into
# replay_cached_messages' `returned_dgs`, so both are unreplayable.
REPLAY_UNSAFE_ELEMENTS = {
    "toast": "EVENT",
    "chat_input": "BOTTOM",
}

CACHE_DECORATORS = {"cache_data", "cache_resource"}

# Directories that are not application code.
_SKIP_PARTS = {"venv", ".venv", "site-packages", "__pycache__", ".git", "tmp"}


def _app_modules() -> list[pathlib.Path]:
    return sorted(
        p
        for p in REPO_ROOT.rglob("*.py")
        if not _SKIP_PARTS.intersection(p.parts)
    )


def _cache_decorator_name(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """The cache decorator on this function, or None.

    Handles both bare `@st.cache_resource` and called
    `@st.cache_resource(show_spinner=False)` forms.
    """
    for dec in node.decorator_list:
        func = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(func, ast.Attribute) and func.attr in CACHE_DECORATORS:
            return func.attr
    return None


def _unsafe_calls_within(node: ast.AST) -> list[tuple[int, str]]:
    """(lineno, element name) for every `st.<unsafe>(...)` inside `node`."""
    found = []
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr in REPLAY_UNSAFE_ELEMENTS
            and isinstance(sub.func.value, ast.Name)
            and sub.func.value.id == "st"
        ):
            found.append((sub.lineno, sub.func.attr))
    return found


def test_scan_actually_covers_the_app():
    """A scan that silently matched nothing would pass forever."""
    modules = _app_modules()
    names = {p.name for p in modules}
    assert "app.py" in names, "app.py must be in scope"
    assert "repo.py" in names, "repo.py must be in scope — it is where this bug was"


def test_no_replay_unsafe_element_inside_a_cached_function():
    offenders: list[str] = []

    for path in _app_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorator = _cache_decorator_name(node)
            if decorator is None:
                continue
            for lineno, element in _unsafe_calls_within(node):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno} — st.{element}() "
                    f"(renders on the {REPLAY_UNSAFE_ELEMENTS[element]} container) "
                    f"inside @st.{decorator} {node.name}()"
                )

    assert not offenders, (
        "A cache-decorated function emits an element that cannot be replayed on a "
        "cache hit; this raises CacheReplayClosureError on the SECOND script run "
        "and every one after, and it will not reproduce locally if the call site "
        "only runs on the hosted deploy.\n\n"
        + "\n".join(offenders)
        + "\n\nFix: record the message and let the CALLER render it — see "
        "repo.pop_cache_hydration_notice() for the worked example."
    )


def test_repo_get_repository_does_not_toast():
    """The specific regression, pinned by name.

    The general scan above would catch it, but this states the actual incident
    so a future reader knows the general rule has a real failure behind it.
    """
    tree = ast.parse((REPO_ROOT / "repo.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "get_repository"
        ):
            assert _cache_decorator_name(node) is not None, (
                "get_repository must stay cache-decorated — it is what "
                "guarantees the Supabase hydration runs once per process"
            )
            assert not _unsafe_calls_within(node), (
                "get_repository() must not call st.toast — it is replayed on "
                "every cache hit and raises CacheReplayClosureError on the "
                "hosted deploy. Use pop_cache_hydration_notice() instead."
            )
            return
    raise AssertionError("repo.get_repository() not found")


def test_hydration_notice_is_drained_once():
    """pop_cache_hydration_notice returns the message exactly once.

    Imports repo lazily so this test does not require streamlit at collection
    time in environments where the rest of the suite runs headless.
    """
    import repo as repo_module

    repo_module._cache_hydration_notice = "Rebuilt the local read cache (x)."
    assert repo_module.pop_cache_hydration_notice() == "Rebuilt the local read cache (x)."
    assert repo_module.pop_cache_hydration_notice() is None
    assert repo_module.pop_cache_hydration_notice() is None


def test_app_renders_the_hydration_notice():
    """app.py must actually drain it, or the rebuild becomes silent.

    Also pins that the drain is NOT nested inside the `offline` branch:
    Repository.offline is `datastore_mode != "cache"`, and cache mode is the
    only mode that ever hydrates, so a drain inside that branch is dead code.
    """
    source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert "pop_cache_hydration_notice()" in source, (
        "app.py must drain the hydration notice — otherwise a cache rebuilt "
        "from Supabase is never reported to the athlete"
    )

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        # `if <...>.offline:` — the offline banner branch.
        test = node.test
        if isinstance(test, ast.Attribute) and test.attr == "offline":
            nested = [
                sub
                for sub in ast.walk(node)
                if isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "pop_cache_hydration_notice"
            ]
            assert not nested, (
                "pop_cache_hydration_notice() is inside `if ....offline:`, where "
                "it can never fire: offline is False in cache mode and cache "
                "mode is the only mode that hydrates."
            )
