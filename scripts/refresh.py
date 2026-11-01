#!/usr/bin/env python3
"""Refresh live.m3u from the curated base list + upstream CN-maintained lists.

* `base.m3u` is the curated, TV-verified list (source of truth, never modified here).
* Upstream lists only *top up* extra lines for channels that already exist.
* Channels are re-sorted into natural order and get `tvg-chno` so the channel
  numbers in the TV app match the real ones (CCTV-1 -> 1, CCTV-2 -> 2, ...).
* No network testing here: CI runs outside mainland China, so its results say
  nothing about reachability from the TV.
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

EXTRA_PER_CHANNEL = 2
BLOCKED_HOST_MARKERS = (
    "74.91.", "63.141.", "204.12.", "45.186.", "38.75.", "61.136.",
    "198.204.", "192.151.",
)

GROUP_ORDER = [
    "\U0001F4FA\u592e\u89c6\u9891\u9053", "\U0001F4E1\u536b\u89c6\u9891\u9053",
    "\U0001F3C0\u4f53\u80b2\u9891\u9053", "\U0001F3AC\u7535\u5f71\u9891\u9053",
    "\U0001FA81\u5c11\u513f\u9891\u9053", "\U0001F4F0\u65b0\u95fb\u9891\u9053",
    "\U0001F4DA\u7eaa\u5f55\u9891\u9053", "\U0001F3B5\u7efc\u827a\u9891\u9053",
    "\U0001F30A\u6e2f\u00b7\u6fb3\u00b7\u53f0",
]

WEISHI_ORDER = [
    "\u5317\u4eac\u536b\u89c6", "\u4e1c\u65b9\u536b\u89c6", "\u6e56\u5357\u536b\u89c6",
    "\u6d59\u6c5f\u536b\u89c6", "\u6c5f\u82cf\u536b\u89c6", "\u5b89\u5fbd\u536b\u89c6",
    "\u5c71\u4e1c\u536b\u89c6", "\u5e7f\u4e1c\u536b\u89c6", "\u6df1\u5733\u536b\u89c6",
    "\u5929\u6d25\u536b\u89c6", "\u91cd\u5e86\u536b\u89c6", "\u56db\u5ddd\u536b\u89c6",
    "\u6e56\u5317\u536b\u89c6", "\u6cb3\u5357\u536b\u89c6", "\u6cb3\u5317\u536b\u89c6",
    "\u8fbd\u5b81\u536b\u89c6", "\u9ed1\u9f99\u6c5f\u536b\u89c6", "\u5409\u6797\u536b\u89c6",
    "\u5c71\u897f\u536b\u89c6", "\u9655\u897f\u536b\u89c6", "\u7518\u8083\u536b\u89c6",
    "\u5b81\u590f\u536b\u89c6", "\u9752\u6d77\u536b\u89c6", "\u65b0\u7586\u536b\u89c6",
    "\u897f\u85cf\u536b\u89c6", "\u4e91\u5357\u536b\u89c6", "\u8d35\u5dde\u536b\u89c6",
    "\u5e7f\u897f\u536b\u89c6", "\u6c5f\u897f\u536b\u89c6", "\u4e1c\u5357\u536b\u89c6",
    "\u6d77\u5357\u536b\u89c6", "\u5185\u8499\u53e4\u536b\u89c6", "\u4e09\u6c99\u536b\u89c6",
    "\u5927\u6e7e\u533a\u536b\u89c6", "\u53a6\u95e8\u536b\u89c6", "\u5ef6\u8fb9\u536b\u89c6",
    "\u5b89\u591a\u536b\u89c6", "\u5eb7\u5df4\u536b\u89c6", "\u5175\u56e2\u536b\u89c6",
    "\u9999\u6e2f\u536b\u89c6",
]

EXTINF = re.compile(r"^#EXTINF.*,([^,]*)$")

GROUP_ALIAS = {
    "\u592e\u89c6\u9891\u9053": GROUP_ORDER[0],
    "\u536b\u89c6\u9891\u9053": GROUP_ORDER[1],
    "\u4f53\u80b2\u9891\u9053": GROUP_ORDER[2],
    "\u7535\u5f71\u9891\u9053": GROUP_ORDER[3],
    "\u5c11\u513f\u9891\u9053": GROUP_ORDER[4],
    "\u65b0\u95fb\u9891\u9053": GROUP_ORDER[5],
    "\u7eaa\u5f55\u9891\u9053": GROUP_ORDER[6],
    "\u7efc\u827a\u9891\u9053": GROUP_ORDER[7],
}


def normalise_group(header: str) -> str:
    g = group_of(header)
    real = GROUP_ALIAS.get(g, g)
    if real != g:
        return re.sub(r'group-title="[^"]*"', 'group-title="%s"' % real, header, count=1)
    return header


def canon(name: str) -> str:
    n = re.sub(r"\[[^\]]*\]", "", name)
    n = re.sub(r"\([^)]*\)", "", n)
    n = re.sub(r"[\s\-_\u00b7]", "", n).lower()
    m = re.fullmatch(r"cctv(\d+)(\+?)", n)
    if m:
        return "cctv%s%s" % (m.group(1), m.group(2))
    return n


def parse(text: str):
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


def group_of(header: str) -> str:
    m = re.search(r'group-title="([^"]*)"', header)
    return m.group(1) if m else ""


def name_of(header: str) -> str:
    m = EXTINF.match(header)
    return m.group(1).strip() if m else ""


def sort_key(header: str):
    group = group_of(header)
    name = name_of(header)
    gi = GROUP_ORDER.index(group) if group in GROUP_ORDER else 99
    if re.match(r"CCTV[- ]?5\+", name):
        return (gi, group, 0, 17.5, name)
    if name.startswith("CCTV-4 Asia"):
        return (gi, group, 0, 17.6, name)
    m = re.match(r"CCTV[- ]?(\d+)$", name)
    if m:
        return (gi, group, 0, float(m.group(1)), name)
    if name.startswith("CGTN"):
        return (gi, group, 1, 0.0, name)
    if name.startswith("CETV"):
        return (gi, group, 2, 0.0, name)
    if group == GROUP_ORDER[1]:
        for i, w in enumerate(WEISHI_ORDER):
            if w in name:
                return (gi, group, 3, float(i), name)
        return (gi, group, 4, 0.0, name)
    return (gi, group, 9, 0.0, name)


def set_chno(header: str, n: int) -> str:
    h = re.sub(r'\s*tvg-chno="[^"]*"', "", header)
    return h.replace("#EXTINF:-1", '#EXTINF:-1 tvg-chno="%d"' % n, 1)


def main() -> int:
    entries = parse(BASE.read_text(encoding="utf-8"))
    if not entries:
        print("base.m3u is empty", file=sys.stderr)
        return 1

    pool = {}
    for url in UPSTREAMS:
        try:
            text = fetch(url)
        except Exception as exc:
            print("skip upstream %s: %s" % (url, exc), file=sys.stderr)
            continue
        for header, urls in parse(text):
            key = canon(name_of(header))
            bucket = pool.setdefault(key, [])
            for u in urls:
                if not blocked(u) and u not in bucket:
                    bucket.append(u)

    entries = [[normalise_group(h), u] for h, u in entries]
    merged = {}
    order = []
    for header, urls in entries:
        k = (group_of(header), canon(name_of(header)))
        if k in merged:
            for u in urls:
                if u not in merged[k][1]:
                    merged[k][1].append(u)
        else:
            merged[k] = [header, list(urls)]
            order.append(k)
    entries = [merged[k] for k in order]
    entries.sort(key=lambda e: sort_key(e[0]))

    lines = ['#EXTM3U x-tvg-url="https://gitee.com/mytv-android/myepg/raw/master/output/epg.gz"']
    added = 0
    counters = {}
    for header, urls in entries:
        group = group_of(header)
        counters[group] = counters.get(group, 0) + 1
        header = set_chno(header, counters[group])

        keep = list(dict.fromkeys(urls))
        for u in pool.get(canon(name_of(header)), []):
            if u in keep:
                continue
            if len(keep) >= len(urls) + EXTRA_PER_CHANNEL:
                break
            keep.append(u)
            added += 1

        lines.append(header)
        lines.extend(keep)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("channels=%d added_upstream_lines=%d -> %s" % (len(entries), added, OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
