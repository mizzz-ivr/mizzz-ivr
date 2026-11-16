"""Optional WRITING widget for Profile Signal.

Fetches the latest public articles from Qiita (public API v2, no auth) and
Zenn (public RSS) and renders them into a profile README between
``PROFILE-SIGNAL:WRITING`` markers. Standard library only.

Design rules:
- Public feeds only. No tokens, no private items (Qiita ``private`` items are
  filtered out even if the API ever returns them).
- Fail-close: when a configured source cannot be fetched, ``build_block``
  returns ``None`` and the caller must keep the previous README block
  untouched. A source that responds with zero articles is *not* a failure;
  the block is simply rendered without that source.
- The widget is intentionally not part of the orchestrator widget registry
  (unknown widget names in ``profile-signal.yml`` fail validation). Consumers
  opt in from their customization step with a small JSON config, e.g.
  ``.github/profile-writing.json``::

      {"enabled": true, "qiita_user": "you", "zenn_user": "", "limit": 3}
"""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

START = "<!-- PROFILE-SIGNAL:WRITING:START -->"
END = "<!-- PROFILE-SIGNAL:WRITING:END -->"
INSERT_BEFORE = "<!-- DEVELOPER-ANALYTICS:START -->"
USER_AGENT = "profile-signal-writing/1.0 (+https://github.com/mizzz-ivr/profile-signal)"
DEFAULT_LIMIT = 3

Opener = Callable[[str], bytes]


def default_opener(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def _clean_title(title: str) -> str:
    return title.replace("[", "(").replace("]", ")").strip()


def fetch_qiita_items(user: str, limit: int = DEFAULT_LIMIT, opener: Opener = default_opener) -> list[dict[str, Any]]:
    url = f"https://qiita.com/api/v2/users/{user}/items?per_page={limit}&page=1"
    payload = json.loads(opener(url).decode("utf-8"))
    items: list[dict[str, Any]] = []
    if not isinstance(payload, list):
        return items
    for raw in payload:
        if not isinstance(raw, dict) or raw.get("private"):
            continue
        tags = [
            str(tag.get("name"))
            for tag in raw.get("tags") or []
            if isinstance(tag, dict) and tag.get("name")
        ]
        items.append(
            {
                "source": "Qiita",
                "title": _clean_title(str(raw.get("title") or "")),
                "url": str(raw.get("url") or ""),
                "date": str(raw.get("created_at") or "")[:10],
                "likes": int(raw.get("likes_count") or 0),
                "tags": tags,
            }
        )
        if len(items) >= limit:
            break
    return items


def fetch_zenn_items(user: str, limit: int = DEFAULT_LIMIT, opener: Opener = default_opener) -> list[dict[str, Any]]:
    url = f"https://zenn.dev/{user}/feed"
    root = ET.fromstring(opener(url).decode("utf-8"))
    items: list[dict[str, Any]] = []
    for node in root.iter("item"):
        title = node.findtext("title") or ""
        link = node.findtext("link") or ""
        pub_date = node.findtext("pubDate") or ""
        date_text = ""
        if pub_date:
            try:
                date_text = parsedate_to_datetime(pub_date).date().isoformat()
            except (TypeError, ValueError):
                date_text = ""
        items.append(
            {
                "source": "Zenn",
                "title": _clean_title(title),
                "url": link.strip(),
                "date": date_text,
                "likes": 0,
                "tags": [],
            }
        )
        if len(items) >= limit:
            break
    return items


def _render_source(heading: str, profile_url: str, handle: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"**{heading}** — [@{html.escape(handle)}]({profile_url})", ""]
    for item in items:
        parts = []
        if item["date"]:
            parts.append(item["date"])
        parts.append(f"[{html.escape(item['title'])}]({item['url']})")
        if item["likes"]:
            parts.append(f"♥ {item['likes']}")
        if item["tags"]:
            parts.append(" ".join(f"`{tag}`" for tag in item["tags"][:3]))
        lines.append("- " + " · ".join(parts))
    lines.append("")
    return lines


def render_writing(
    qiita_items: list[dict[str, Any]],
    zenn_items: list[dict[str, Any]],
    qiita_user: str = "",
    zenn_user: str = "",
) -> str:
    lines = [START, "## WRITING // Latest articles", ""]
    if qiita_items:
        lines.extend(_render_source("Qiita", f"https://qiita.com/{qiita_user}", qiita_user, qiita_items))
    if zenn_items:
        lines.extend(_render_source("Zenn", f"https://zenn.dev/{zenn_user}", zenn_user, zenn_items))
    while lines and lines[-1] == "":
        lines.pop()
    lines.append(END)
    return "\n".join(lines)


def build_block(config: dict[str, Any], opener: Opener = default_opener) -> str | None:
    """Return the rendered WRITING block, or None to keep the previous one.

    None is returned when any configured source fails to fetch, or when no
    source yields any article.
    """
    limit = int(config.get("limit") or DEFAULT_LIMIT)
    qiita_user = str(config.get("qiita_user") or "")
    zenn_user = str(config.get("zenn_user") or "")
    qiita_items: list[dict[str, Any]] = []
    zenn_items: list[dict[str, Any]] = []
    try:
        if qiita_user:
            qiita_items = fetch_qiita_items(qiita_user, limit, opener)
        if zenn_user:
            zenn_items = fetch_zenn_items(zenn_user, limit, opener)
    except Exception:
        return None
    if not qiita_items and not zenn_items:
        return None
    return render_writing(qiita_items, zenn_items, qiita_user, zenn_user)


def update_readme_text(text: str, block: str) -> str:
    if START in text and END in text:
        pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
        return pattern.sub(lambda _match: block, text, count=1)
    if INSERT_BEFORE in text:
        return text.replace(INSERT_BEFORE, block + "\n\n" + INSERT_BEFORE, 1)
    return text.rstrip() + "\n\n" + block + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Update the WRITING widget in a profile README")
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--qiita-user", default="")
    parser.add_argument("--zenn-user", default="")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()
    config = {"qiita_user": args.qiita_user, "zenn_user": args.zenn_user, "limit": args.limit}
    block = build_block(config)
    if block is None:
        print("Writing widget: skipped (fetch failed or no public articles); README unchanged")
        return
    text = args.readme.read_text(encoding="utf-8")
    args.readme.write_text(update_readme_text(text, block), encoding="utf-8")
    print("Writing widget: updated", f"qiita={args.qiita_user or '-'}", f"zenn={args.zenn_user or '-'}")


if __name__ == "__main__":
    main()
