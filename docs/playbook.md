# playbook.md — Reusable Recipes

Patterns that came up during Phases 1-4. Copy-paste when needed.

---

## 1. PowerShell commit with multiline message

PowerShell 5.1 does not support bash `<<'EOF'` heredoc in `git commit -m "$(cat <<'EOF'...)"`.

```powershell
$msg = @'
Short subject line

Body paragraph if needed.
Why this change was made.
'@
git commit -m $msg
```

- The closing `'@` **must be at column 0** — no leading whitespace.
- Use single-quote heredoc (`@'...'@`) to prevent `$`/backtick expansion inside the message.
- Avoid path strings with quotes or slashes in the subject line — git may interpret them as pathspecs.

---

## 2. Stage a specific file and commit it alone

```powershell
git add path/to/file.py
git diff --cached --stat   # verify only that file is staged
git commit -m $msg
```

Avoid `git add -A` or `git add .` — they can sweep in secrets (`.streamlit/secrets.toml`, `.env`).

---

## 3. git mv for tracked files vs Copy-Item for untracked

`git mv` only works on files git already tracks:

```powershell
# Tracked file (safe to git mv):
git mv legacy_file.py legacy/legacy_file.py
git commit -m "G2: move legacy_file.py to legacy/"

# Untracked file (git mv will fail — use Copy-Item instead):
Copy-Item "Training plan\file.md" "docs\training\file.md"
git add docs/training/file.md
git commit -m "G4: copy Training plan/file.md to docs/training/"
# Then manually delete the source — sandbox rules block Remove-Item.
```

---

## 4. Import-fix pattern for duplicate constants

When two files define the same constant:

1. Identify the canonical home (the module that *owns* the concept).
2. In the consuming file, delete the inline definition.
3. Add `from canonical_module import CONSTANT_NAME` at the top.
4. Run `python tests.py` to confirm no break.

Example from G1:
```python
# views/checkin.py — BEFORE (32 lines of inline definitions)
ANATOMICAL_LOCATIONS = ["Lower back (left)", "Lower back (right)", ...]
SENSATION_TAGS = ["Tightness", "Aching", ...]

# views/checkin.py — AFTER (one line)
from training_constants import ANATOMICAL_LOCATIONS, SENSATION_TAGS
```

---

## 5. Gate sequence (before every commit)

```powershell
python tests.py
```

Check output: `X/141 passed` — must be 141/141 before committing any logic change.

For file-only moves (no logic change), run the gate anyway to catch accidental breaks.

---

## 6. Verify no secrets in git history

```powershell
git log --all -- ".streamlit/secrets.toml"  # should return empty
git log --all -- "*.toml"
git log --all -S "NOTION_TOKEN"             # search for literal string in all commits
```

If a secret appears in history, it must be rotated immediately, then removed from history via `git filter-branch` or `git filter-repo` (confirm with user before running — destructive).

---

## 7. Make a `__file__`-relative path in a moved script

When a script is moved to a subdirectory but must still find a sibling file:

```python
# Before (breaks after move):
SCHEMA_PATH = "schema.sql"

# After (always resolves relative to the script itself):
import os
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
```

---

## 8. Derive per-stage ceiling from rules instead of hardcoding

```python
# Bad — hardcoded, diverges from rules.py:
ceiling = 1.2 if stage == 1 else 1.3

# Good — single source of truth:
import rules as _rules
ceiling = _rules.STAGE_CONSTRAINTS.get(stage, {}).get("acwr_ceiling", 1.3)
```

`rules.py` has zero internal imports, so there is no circular import risk.

---

## 9. Check for circular imports before adding a cross-module import

```powershell
python -c "import engine"   # should complete silently if no circular import
python -c "import rules"
python -c "import app"
```

---

## 10. Untracked file cleanup (Training plan/ stale duplicate)

The sandbox deny rules block `Remove-Item -Recurse` and `rm -rf`. To clean up untracked stale directories, the user must run manually in their own terminal:

```powershell
Remove-Item -Recurse -Force "Training plan"
```

Or in bash:
```bash
rm -rf "Training plan"
```

After deletion, `git status` should no longer show `??  Training plan/`.
