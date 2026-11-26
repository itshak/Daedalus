"""Stage an exact, CI-verified main revision as an unpublished GitHub beta.

Requires the operator's already authorized GitHub CLI. No production access,
secret extraction, tag movement, stable publishing, or backend deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO = "itshak/Daedalus"
WORKFLOWS = ("CI", "Source package checks", "Public source security", "Web control center",
             "Native desktop smoke", "Vendored IkaBot engine", "Native macOS app preview")
DMG = "Daedalus-macos-preview.dmg"


def command(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, timeout=300).stdout.strip()


def require_green(runs, sha):
    for name in WORKFLOWS:
        matching = [r for r in runs if r.get("name") == name and r.get("headSha") == sha]
        if not matching or matching[0].get("status") != "completed" or matching[0].get("conclusion") != "success":
            raise ValueError(f"Missing successful latest main workflow: {name}")


def verify_checksum(path, checksum):
    match = re.fullmatch(r"([a-f0-9]{64}) [ *]" + re.escape(DMG) + r"\s*", checksum.read_text(encoding="ascii"))
    if not match or path.name != DMG or path.stat().st_size <= 0:
        raise ValueError("Invalid DMG checksum manifest")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != match.group(1):
        raise ValueError("DMG checksum mismatch")
    return actual


def require_refreshable_draft(release, tag, existing_tag):
    if (existing_tag or release.get("tagName") != tag or release.get("isDraft") is not True
            or release.get("isPrerelease") is not True):
        raise ValueError("Refusing to replace a published release, non-beta draft, or existing tag")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True, help="Exact approved main commit SHA")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--create-draft", action="store_true", help="Create an unpublished prerelease draft after verification")
    mode.add_argument("--refresh-draft", action="store_true", help="Refresh only an existing unpublished beta draft after verification")
    args = parser.parse_args()
    sha = args.revision
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        parser.error("Expected a full commit SHA")
    root = Path(__file__).resolve().parents[1]
    if command("git", "rev-parse", "HEAD", cwd=root) != sha or command("git", "status", "--porcelain", cwd=root):
        raise SystemExit("Run from a clean checkout of the exact approved revision")
    if command("gh", "api", f"repos/{REPO}/git/ref/heads/main", "--jq", ".object.sha") != sha:
        raise SystemExit("The approved revision is no longer main")
    version = json.loads((root / "apps/web/package.json").read_text(encoding="utf-8"))["version"]
    if not re.fullmatch(r"0\.1\.0-beta\.[1-9][0-9]*", version):
        raise SystemExit("Expected first beta version metadata")
    tag = "v" + version
    runs = json.loads(command("gh", "run", "list", "--repo", REPO, "--branch", "main", "--commit", sha,
                              "--limit", "100", "--json", "name,headSha,status,conclusion,event,databaseId"))
    require_green(runs, sha)
    preview = "desktop-preview-" + sha[:12]
    if command("gh", "api", f"repos/{REPO}/commits/{preview}", "--jq", ".sha") != sha:
        raise SystemExit("Preview tag does not resolve to the approved source revision")
    with tempfile.TemporaryDirectory(prefix="daedalus-release-") as directory:
        folder = Path(directory)
        command("gh", "release", "download", preview, "--repo", REPO, "--pattern", DMG, "--pattern", DMG + ".sha256", "--dir", directory)
        digest = verify_checksum(folder / DMG, folder / (DMG + ".sha256"))
        print(f"Verified {tag} source {sha}; DMG SHA-256 {digest}")
        if not (args.create_draft or args.refresh_draft):
            return
        # No published release or existing tag may be moved. The explicit
        # refresh path only replaces an unpublished candidate for this version.
        existing = subprocess.run(["gh", "release", "view", tag, "--repo", REPO,
                                   "--json", "tagName,isDraft,isPrerelease,targetCommitish"],
                                  capture_output=True, text=True, timeout=30, check=False)
        existing_tag = command("git", "ls-remote", "--tags", "origin", "refs/tags/" + tag, cwd=root)
        if args.refresh_draft:
            if existing.returncode != 0:
                raise SystemExit("Existing draft unavailable; cannot refresh")
            require_refreshable_draft(json.loads(existing.stdout), tag, existing_tag)
        elif existing.returncode == 0 or existing_tag:
            raise SystemExit("Versioned release or tag already exists; inspect it manually")
        notes = folder / "notes.md"
        notes.write_text((root / "CHANGELOG.md").read_text(encoding="utf-8") +
                         f"\nSource revision: `{sha}`\n\nDMG SHA-256: `{digest}`\n\n"
                         "Unnotarized beta candidate. Owner acceptance and coordinated deployment are pending.\n"
                         "See https://github.com/itshak/Daedalus/issues/60 and docs/BETA-OPERATION-SCOPE.md.\n", encoding="utf-8")
        if args.refresh_draft:
            # Keep the release unpublished. If asset upload fails, the draft
            # must be checked again; never publish from this script.
            command("gh", "release", "upload", tag, str(folder / DMG), str(folder / (DMG + ".sha256")),
                    "--repo", REPO, "--clobber")
            print(command("gh", "release", "edit", tag, "--repo", REPO, "--target", sha,
                          "--draft=true", "--prerelease", "--notes-file", str(notes)))
            observed = json.loads(command("gh", "release", "view", tag, "--repo", REPO,
                                          "--json", "tagName,isDraft,isPrerelease,targetCommitish,assets"))
            require_refreshable_draft(observed, tag, "")
            if observed.get("targetCommitish") != sha or {a["name"] for a in observed["assets"]} != {DMG, DMG+".sha256"}:
                raise SystemExit("Refreshed draft metadata does not match the candidate")
            # Verify the actual uploaded draft bytes, not just the local copy.
            fetched = folder / "draft-verification"
            fetched.mkdir()
            command("gh", "release", "download", tag, "--repo", REPO, "--pattern", DMG,
                    "--pattern", DMG+".sha256", "--dir", str(fetched))
            if verify_checksum(fetched/DMG, fetched/(DMG+".sha256")) != digest:
                raise SystemExit("Refreshed draft checksum differs from approved preview")
            return
        print(command("gh", "release", "create", tag, str(folder / DMG), str(folder / (DMG + ".sha256")),
                      "--repo", REPO, "--target", sha, "--draft", "--prerelease", "--title", "Daedalus " + version,
                      "--notes-file", str(notes)))


if __name__ == "__main__":
    main()
