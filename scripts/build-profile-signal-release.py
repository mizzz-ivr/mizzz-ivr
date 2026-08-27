#!/usr/bin/env python3
"""Build a self-contained Profile Signal release archive."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".profile-signal"
DISTRIBUTION = ROOT / "distribution"
DIST = ROOT / "dist"

REQUIRED_RUNTIME = (
    "action.yml",
    "LICENSE",
    "src/orchestrator.py",
    "src/preset_runtime.py",
    "scripts/update-profile-activity.py",
    "scripts/profile_signal.py",
    "scripts/update-profile-signal.py",
    "scripts/profile_signal_operations.py",
    "scripts/profile_signal_history.py",
)
REQUIRED_PRESETS = (
    "minimal.yml",
    "standard.yml",
    "full.yml",
    "terminal.yml",
    "compact.yml",
    "developer.yml",
    "activity.yml",
    "oss.yml",
)


def normalize_version(value: str) -> str:
    version = value.strip()
    if not version:
        raise ValueError("version must not be empty")
    return version if version.startswith("v") else f"v{version}"


def validate_sources() -> None:
    missing = [path for path in REQUIRED_RUNTIME if not (RUNTIME / path).is_file()]
    missing.extend(
        f"presets/{name}"
        for name in REQUIRED_PRESETS
        if not (RUNTIME / "presets" / name).is_file()
    )
    for path in ("profile-signal.yml", "profile-signal-workflow.yml", "INSTALL.md"):
        if not (DISTRIBUTION / path).is_file():
            missing.append(f"distribution/{path}")
    if missing:
        raise RuntimeError("Missing release source files: " + ", ".join(missing))


def build(version: str) -> Path:
    validate_sources()
    version = normalize_version(version)
    DIST.mkdir(parents=True, exist_ok=True)
    archive = DIST / f"profile-signal-{version}.zip"

    with tempfile.TemporaryDirectory(prefix="profile-signal-") as temp_dir:
        root = Path(temp_dir) / "profile-signal"
        shutil.copytree(RUNTIME, root / ".profile-signal")

        github_dir = root / ".github"
        workflows_dir = github_dir / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DISTRIBUTION / "profile-signal.yml", github_dir / "profile-signal.yml")
        shutil.copy2(
            DISTRIBUTION / "profile-signal-workflow.yml",
            workflows_dir / "profile-signal.yml",
        )
        shutil.copy2(DISTRIBUTION / "INSTALL.md", root / "PROFILE_SIGNAL_INSTALL.md")
        (root / "PROFILE_SIGNAL_VERSION").write_text(version + "\n", encoding="utf-8")

        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(root)
                info = zipfile.ZipInfo.from_file(path, arcname=str(relative))
                info.date_time = (2026, 1, 1, 0, 0, 0)
                with path.open("rb") as source:
                    zf.writestr(info, source.read(), compress_type=zipfile.ZIP_DEFLATED)

    return archive


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    archive = build(args.version)
    print(archive.relative_to(ROOT))


if __name__ == "__main__":
    main()
