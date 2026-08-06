"""
check_cluster_documents.py — run every movement named in the Cluster A
documents through services.rules.check_movement at the athlete's live stage.

WHY THIS EXISTS. On 2026-08-06 an audit of the (then unadapted) Cluster A
source documents against services/rules.py found that of 78 movement names,
8 matched any rule at all, 70 returned `unknown` — which is not a block — and
zero of the 14 movements contraindicated on mechanism were caught by the rule
written for them. One instruction ("hands walking forward") was affirmatively
returned as `cleared` off the `walking` keyword.

The matcher and the vocabulary are fixed and the documents are adapted. This
script is what keeps both true: it is the check that a later edit to any of the
three documents cannot quietly reintroduce a movement the rule set does not
recognise, or one it recognises and forbids.

    python scripts/check_cluster_documents.py

Exit code 0 when every named movement resolves to `cleared` or `caution`,
1 otherwise. `Input_files/` is gitignored, so this is also the only durable
record of the check having been run — keep the output with the commit.

NOTE ON GITIGNORE. `Input_files/` is excluded from git, and ripgrep honours
.gitignore by default. Any search over these documents needs --no-ignore, or it
will silently report that they contain nothing.
"""

from __future__ import annotations

import io
import os
import re
import sys

# The documents are full of em dashes and the ⟦A⟧ adaptation markers, and a
# Windows console defaults to cp1252 — which raises rather than substituting.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import rules  # noqa: E402

DOCS = (
    "Input_files/assessment_battery.md",
    "Input_files/cluster_a_mechanics.md",
    "Input_files/cluster_a_prescription.md",
)

#: The athlete's live stage. Held here rather than read from Notion so the
#: script runs offline; `patient_profile.PROFILE["current_stage"]` is the
#: clinical record and Repository.get_current_stage() is the runtime value.
STAGE = 2

_STRIP = (
    re.compile(r"⟦[^⟧]*⟧"),                     # adaptation markers
    re.compile(r"\*\([^)]*\)\*"),                # *(deferred)*, *(removed …)*
    re.compile(r"[★*_`]"),                       # emphasis and source marks
)

#: Items that reference a block, a deferral or an absence rather than naming a
#: movement to perform. Structural, not a vocabulary list.
_NOT_AN_INSTRUCTION = re.compile(
    r"pre-session release block|deferred (past|until)|removed", re.I)

#: The three measures. A "Test" column holds these in the spectrum table and
#: movement names in the leverage table, so the column header alone cannot tell
#: them apart. Imported rather than retyped, so this cannot drift.
_MEASURE_WORDS = {"passive", "isometric", "active"}


def _clean(raw: str) -> str:
    """Reduce a cell or list item to the movement's name alone."""
    name = raw
    for pattern in _STRIP:
        name = pattern.sub("", name)
    # The dose, cue and rationale after an em dash are not part of the name.
    name = re.split(r"\s+[—–]\s+|\s+\d+\s*[×x]\s*\d+", name)[0]
    return name.strip(" .,:()")


def movement_names(text: str) -> list[str]:
    """Every string in the document that names a movement to perform.

    Two shapes carry them, and both are identified STRUCTURALLY rather than by
    a vocabulary list — a filter built from words would need updating every
    time a document gains one, and would fail open when it wasn't.

      1. A row of a table whose HEADER names an exercise or test column. The
         header is what makes this safe: the documents are full of tables about
         method, patterns and revert conditions, and none of those declare an
         exercise column.
      2. A numbered list item with a bolded head — the shape every stack item
         in the Prescription takes.
    """
    found: list[str] = []
    header: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()

        item = re.match(r"^\d+\.\s+\*\*(.+?)\*\*", stripped)
        if item and not _NOT_AN_INSTRUCTION.search(item.group(1)):
            found.append(item.group(1))
            continue

        if not stripped.startswith("|"):
            header = []
            continue
        if set(stripped) <= set("|- :"):        # the |---|---| separator
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]
        lowered = [c.lower() for c in cells]

        # A header row declares the columns; remember it and move on.
        if any(h in lowered for h in ("exercise", "test", "zone", "leverage")) \
                or any(h in lowered for h in ("why", "reverts when", "what changed",
                                              "removed", "reading", "result",
                                              "measure", "limiter", "stack",
                                              "pattern", "value", "component",
                                              "evidence", "fix", "mistake",
                                              "instruction", "location", "loaded?")):
            header = lowered
            continue

        if not header:
            continue
        for column in ("exercise", "test"):
            if column in header:
                found.append(cells[header.index(column)])
                break

    out = []
    for raw in found:
        name = _clean(raw)
        if len(name) < 3:
            continue
        # A question is a decision the reader makes, not a movement performed.
        if name.endswith("?"):
            continue
        # The spectrum table names measures in its Test column.
        if name.lower().strip("*") in _MEASURE_WORDS:
            continue
        if _NOT_AN_INSTRUCTION.search(name):
            continue
        out.append(name)
    return out


def main() -> int:
    worst: list[tuple[str, str, str]] = []
    total = 0

    for path in DOCS:
        if not os.path.exists(path):
            print(f"MISSING {path} — is Input_files/ present?")
            return 1
        text = io.open(path, encoding="utf-8").read()
        names = movement_names(text)
        print(f"\n=== {path} — {len(names)} named movements ===")
        for name in names:
            total += 1
            verdict = rules.check_movement(name, STAGE)
            severity = verdict["severity"]
            if severity in ("unknown", "contraindicated"):
                worst.append((path, name, severity))
                print(f"  !! {severity:17s} {name[:64]}")
            else:
                print(f"     {severity:17s} {name[:64]}")

    print(f"\n{total} movements checked at stage {STAGE}.")
    if worst:
        print(f"\n{len(worst)} PROBLEM(S):")
        for path, name, severity in worst:
            print(f"  {severity:17s} {name}   [{path}]")
        print("\n`unknown` means the rule set does not recognise it — add a rule.")
        print("`contraindicated` means it must not appear in an adapted document.")
        return 1

    print("All named movements resolve to cleared or caution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
