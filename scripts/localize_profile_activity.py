from __future__ import annotations

import argparse
import re
from pathlib import Path

STREAM_START = "<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:START -->"
STREAM_END = "<!-- PROFILE-SIGNAL:ACTIVITY-STREAM:END -->"


def localize_event_title(title: str) -> str:
    patterns: tuple[tuple[re.Pattern[str], object], ...] = (
        (
            re.compile(r"^(\d+) commits? pushed to (.+)$", re.IGNORECASE),
            lambda match: f"{match.group(2)}へ{match.group(1)}コミットをPush",
        ),
        (
            re.compile(r"^PR merged #(\d+)$", re.IGNORECASE),
            lambda match: f"PR #{match.group(1)}をマージ",
        ),
        (
            re.compile(r"^(?:Opened PR|PR opened) #(\d+)$", re.IGNORECASE),
            lambda match: f"PR #{match.group(1)}を作成",
        ),
        (
            re.compile(r"^Opened issue #(\d+)$", re.IGNORECASE),
            lambda match: f"Issue #{match.group(1)}を作成",
        ),
        (
            re.compile(r"^Closed issue #(\d+)$", re.IGNORECASE),
            lambda match: f"Issue #{match.group(1)}を完了",
        ),
        (
            re.compile(r"^Released (.+)$", re.IGNORECASE),
            lambda match: f"{match.group(1)}をリリース",
        ),
    )
    for pattern, formatter in patterns:
        match = pattern.fullmatch(title.strip())
        if match:
            return formatter(match)  # type: ignore[operator]
    return title


def localize_stream_block(block: str) -> str:
    anchor_pattern = re.compile(r"(<a\b[^>]*>)(.*?)(</a>)", re.DOTALL)

    def replace_anchor(match: re.Match[str]) -> str:
        original = match.group(2)
        localized = localize_event_title(original)
        return f"{match.group(1)}{localized}{match.group(3)}"

    return anchor_pattern.sub(replace_anchor, block)


def localize_readme(text: str) -> str:
    if STREAM_START not in text or STREAM_END not in text:
        raise ValueError("Activity Stream marker pair is missing")
    start = text.index(STREAM_START)
    end = text.index(STREAM_END, start) + len(STREAM_END)
    block = text[start:end]
    return text[:start] + localize_stream_block(block) + text[end:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Localize known Profile Signal activity titles for the Japanese profile")
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    args = parser.parse_args()
    current = args.readme.read_text(encoding="utf-8")
    localized = localize_readme(current)
    if localized != current:
        args.readme.write_text(localized, encoding="utf-8")
    print("Localized known Profile Signal activity titles")


if __name__ == "__main__":
    main()
