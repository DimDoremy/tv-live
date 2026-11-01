#!/usr/bin/env python3
"""Refresh live.m3u from the curated base list + upstream CN-maintained lists.

Design notes
------------
* `base.m3u` is the curated, TV-verified list. It is the source of truth and is
  never modified by this script.
* Upstream lists are only used to *top up* extra lines for channels that already
  exist in the base list — they never introduce new channels or web/WebView
  entries.
* No network testing happens here on purpose: the CI runner is outside mainland
  China, so reachability from the runner says nothing about reachability from the
  TV. Only the maintainer's TV-side test result should remove lines.
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "base.m3u"
OUT = ROOT / "live.m3u"

UPSTREAMS = [
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u",
]

EXTRA_PER_CHANNEL = 2          # how many upstream lines may be added per channel
BLOCKED_HOST_MARKERS = (        # known slow / unstable relays (kept out of base too)
    "74.91.", "63.141.", "204.12.", "45.186.", "38.75.", "61.136.",
    "198.204.", "192.151.",
)

EXTINF = re.compile(r"^#EXTINF.*,([^,]*)$")


def canon(name: str) -> str:
    n = re.sub(r"\[[^\]]*\]", "", name)
    n = re.sub(r"\([^)]*\)", "", n)
    n = re.sub(r"[\s\-_·]", "", n).lower()
    m = re.fullmatch(r"cctv(\d+)(\+?)", n)
    if m:
        return f"cctv{m.group(1)}{m.group(2)}"
    return n


def parse(text: str):
    """-> list of (header_line, [urls])"""
    out, cur = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            cur = [line, []]
            out.append(cur)
        elif line.startswith("#"):
            continue
        elif line.startswith("http") and cur is not None:
            cur[1].append(line)
    return out


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "tv-live-refresh/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def blocked(url: str) -> bool:
    return any(m in url for m in BLOCKED_HOST_MARKERS)


def main() -> int:
    base_text = BASE.read_text(encoding="utf-8")
    entries = parse(base_text)
    if not entries:
        print("base.m3u is empty", file=sys.stderr)
        return 1

    upstream_pool: dict[str, list[str]] = {}
    for url in UPSTREAMS:
        try:
            text = fetch(url)
        except Exception as exc:                      # noqa: BLE001
            print(f"skip upstream {url}: {exc}", file=sys.stderr)
            continue
        for header, urls in parse(text):
            name = EXTINF.match(header)
            if not name:
                continue
            key = canon(name.group(1))
            bucket = upstream_pool.setdefault(key, [])
            for u in urls:
                if not blocked(u) and u not in bucket:
                    bucket.append(u)

    added = 0
    lines = ['#EXTM3U x-tvg-url="https://gitee.com/mytv-android/myepg/raw/master/output/epg.gz"']
    for header, urls in entries:
        name = EXTINF.match(header)
        key = canon(name.group(1)) if name else ""
        keep = list(dict.fromkeys(urls))
        extra = [u for u in upstream_pool.get(key, []) if u not in keep]
        for u in extra[:EXTRA_PER_CHANNEL]:
            keep.append(u)
            added += 1
        lines.append(header)
        lines.extend(keep)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"channels={len(entries)} added_upstream_lines={added} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
