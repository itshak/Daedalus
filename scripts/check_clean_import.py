"""Ensure forbidden private runtime filenames are absent from tracked Git sources."""

import subprocess
from pathlib import PurePosixPath

FORBIDDEN_NAMES = {
    "tokens.json",
    "cookies.json",
    "credentials.json",
    "secrets.json",
    "session.json",
}
FORBIDDEN_PARTS = {"accounts", "browser-profiles", "runtime", "state", "logs"}


def main() -> int:
    completed = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, check=True
    )
    bad: list[str] = []
    for raw_name in completed.stdout.split(b"\0"):
        if not raw_name:
            continue
        name = raw_name.decode("utf-8", errors="replace")
        parts = PurePosixPath(name).parts
        if (
            name.endswith((".pem", ".p12", ".pfx", ".key", ".cookie", ".session", ".env"))
            or any(part.startswith(".env.") and part != ".env.example" for part in parts)
            or any(part in FORBIDDEN_PARTS for part in parts)
            or PurePosixPath(name).name in FORBIDDEN_NAMES
        ):
            bad.append(name)
    if bad:
        print("Forbidden tracked paths:\n" + "\n".join(sorted(bad)))
        return 1
    print("Tracked runtime and credential path check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
