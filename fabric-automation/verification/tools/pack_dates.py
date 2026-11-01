"""Compares the 'Updated' column of the reference files with the updated_at meta of the live pages.

usage: python pack_dates.py PACKDIR

PACKDIR holds the reference files (toolchain/skills/factory-standards/references). Each page of Microsoft Learn carries two dates in its markup: ms.date, which the
author sets, and updated_at, which is set when the page is published. The pack records updated_at, because it is the one that moves when the text changes. This
reads each page once (a public read, no sign-in) and prints ok or MISMATCH for it. It needs the network.
"""
import re
import sys
import urllib.request
from pathlib import Path

seen = {}
for path in sorted(Path(sys.argv[1]).glob("*.md")):
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 4 and cells[1].startswith("https://learn.microsoft.com/") and cells[0] != "Label":
            seen.setdefault(cells[1], set()).add((path.name, cells[2]))
bad = 0
for url, uses in sorted(seen.items()):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (pack-dates)"})
    html = urllib.request.urlopen(request, timeout=60).read().decode("utf-8", "replace")
    updated = re.search(r'<meta name="updated_at" content="([^"]+)"', html)
    msdate = re.search(r'<meta name="ms.date" content="([^"]+)"', html)
    updated = updated.group(1)[:10] if updated else "none"
    msdate = msdate.group(1)[:10] if msdate else "none"
    dates = {d for _, d in uses}
    flag = "ok" if dates == {updated} else "MISMATCH"
    if flag != "ok":
        bad += 1
    print("%-8s updated_at=%s ms.date=%s pack=%s %s" % (flag, updated, msdate, ",".join(sorted(dates)), url.split("learn.microsoft.com/")[1]))
print("%d page(s), %d mismatch(es)" % (len(seen), bad))
sys.exit(1 if bad else 0)
