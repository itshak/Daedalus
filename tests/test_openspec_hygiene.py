"""Regression guard: OpenSpec archival claims must match checked tasks and docs.

These checks read repository-local Markdown only. They do not require a live
game session, browser, credentials, or network access.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGES = ROOT / "openspec" / "changes"
SPECS = ROOT / "openspec" / "specs"
STATUS = ROOT / "docs" / "PROJECT-STATUS.md"


def _tasks(path: Path) -> tuple[int, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    checked = sum(line.lstrip().startswith("- [x] ") for line in lines)
    unchecked = sum(line.lstrip().startswith("- [ ] ") for line in lines)
    return checked, unchecked


def test_archived_changes_complete_or_have_exact_supersession_dispositions():
    archives = sorted((CHANGES / "archive").glob("*/tasks.md"))
    assert archives, "Archived changes must have historical task evidence"
    index = ROOT / "docs" / "V010-RECONCILIATION.md"
    owner = ROOT / "docs" / "V010-OWNER-ACCEPTANCE.md"
    for path in archives:
        checked, unchecked = _tasks(path)
        if not unchecked:
            assert checked > 0, f"Archived change lacks completed tasks: {path.parent.name}"
            continue
        disposition = path.with_name("consolidation-record.md")
        assert disposition.is_file(), f"Unchecked tasks lack explicit disposition: {path.parent.name}"
        content = disposition.read_text(encoding="utf-8")
        tasks = [line.lstrip()[6:] for line in path.read_text(encoding="utf-8").splitlines()
                 if line.lstrip().startswith("- [ ] ")]
        mapped = re.findall(r"^\| (\d+)\. (.*?) \| ([^|]+?) \|$", content, re.MULTILINE)
        assert len(mapped) == unchecked
        for i, (number, text, codes) in enumerate(mapped, 1):
            assert int(number) == i
            assert text.replace(r"\|", "|") == tasks[i - 1]
            for code in codes.split("; "):
                assert re.fullmatch(r"V[1-8]|E[1-6]|O[1-6]|S", code), code
                if code.startswith("O"):
                    assert f"## {code} —" in owner.read_text(encoding="utf-8")
                elif code.startswith("E"):
                    successor = CHANGES / "finish-v010-engineering" / "tasks.md"
                    if not successor.exists():
                        successor = next((CHANGES / "archive").glob("*-finish-v010-engineering/tasks.md"))
                    assert f"## {code} —" in successor.read_text(encoding="utf-8")
                else:
                    assert f"**{code}**" in index.read_text(encoding="utf-8")
        assert path.parent.name in index.read_text(encoding="utf-8")


def test_superseded_delta_requirements_have_canonical_dispositions():
    index = (ROOT / "docs" / "V010-RECONCILIATION.md").read_text(encoding="utf-8")
    renamed = {
        "Opt-in automatic recovery after a confirmed rotation grace period":
            "Confirmed rotation grace period for automatic recovery",
        "Automatic headless Gameforge authentication with human CAPTCHA only":
            "Observable headless Gameforge authentication with visible failure recovery",
    }
    for record in sorted((CHANGES / "archive").glob("*/consolidation-record.md")):
        change = record.parent.name.split("-", 3)[-1]
        for delta in record.parent.glob("specs/*/spec.md"):
            capability = delta.parent.name
            canonical = (SPECS / capability / "spec.md").read_text(encoding="utf-8")
            for title in re.findall(r"^### Requirement: (.+)$", delta.read_text(encoding="utf-8"), re.MULTILINE):
                assert f"| {change} | {capability} | {title} |" in index
                assert f"### Requirement: {renamed.get(title, title)}" in canonical.splitlines()


def test_every_active_change_is_explicitly_unfinished_and_reported():
    active = sorted(CHANGES.glob("*/tasks.md"))
    status = STATUS.read_text(encoding="utf-8")
    if not active:
        assert "No active OpenSpec implementation changes" in status, (
            "Zero active changes must be disclosed explicitly"
        )
        assert "issues/60" in status and "NOT TESTED / NOT APPROVED" in status, (
            "Human-only acceptance must remain tracked separately from code closure"
        )
    for path in active:
        _checked, unchecked = _tasks(path)
        assert unchecked > 0, f"Complete change must be archived: {path.parent.name}"
        assert f"`{path.parent.name}`" in status, (
            f"Unfinished change is not disclosed in docs/PROJECT-STATUS.md: {path.parent.name}"
        )


def test_canonical_capability_specs_exist_for_all_active_deltas():
    """New ADDED capabilities become canonical only after implementation/archive."""
    for path in sorted(CHANGES.glob("*/specs/*/spec.md")):
        capability = path.parent.name
        if (SPECS / capability / "spec.md").is_file():
            continue
        delta = path.read_text(encoding="utf-8")
        operations = re.findall(
            r"^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements\s*$",
            delta,
            flags=re.MULTILINE,
        )
        assert operations == ["ADDED"], (
            f"Unrecognized capability {capability} may only have ADDED requirements: {path}"
        )
        assert "## Purpose" in delta, (
            f"New capability {capability} needs a Purpose before archival"
        )



def test_project_status_inventory_matches_the_archive():
    archives = sorted(p.name.split("-", 3)[-1] for p in (CHANGES / "archive").iterdir() if p.is_dir())
    status = STATUS.read_text(encoding="utf-8")
    rows = re.findall(r"^\| \`([^\`]+)\` \|", status, flags=re.MULTILINE)
    assert len(rows) == len(set(rows)), "Project status repeats an archived change"
    assert sorted(rows) == archives, "Project status must list every archived change"



def test_archived_capability_specs_have_canonical_targets():
    for path in sorted((CHANGES / "archive").glob("*/specs/*/spec.md")):
        capability = path.parent.name
        assert (SPECS / capability / "spec.md").is_file(), (
            f"Archived delta {path} has no canonical capability spec"
        )
