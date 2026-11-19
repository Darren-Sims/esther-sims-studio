#!/usr/bin/env python3
"""Check site/: every local link resolves to a file, and list remaining external hosts."""
import html
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE = Path(__file__).resolve().parent.parent / "site"
DOMAIN_HOSTS = {"www.esthersimsstudio.co.uk", "esthersimsstudio.co.uk"}
PAGES = {"/" if p.name == "index.html" else "/" + p.relative_to(SITE).with_suffix("").as_posix()
         for p in SITE.rglob("*.html")}

missing, external = [], Counter()


def check(url, where):
    url = html.unescape(url).strip()
    if not url or url.startswith(("#", "mailto:", "tel:", "data:", "javascript:", "${")):
        return
    parts = urlsplit(url)
    if parts.scheme in ("http", "https") or url.startswith("//"):
        if parts.netloc in DOMAIN_HOSTS:
            path = parts.path or "/"
        else:
            external[parts.netloc] += 1
            return
    else:
        path = parts.path
    if not path.startswith("/"):
        missing.append((where, url, "relative path left"))
        return
    path = unquote(path)
    if path in PAGES or path.rstrip("/") in PAGES:
        return
    if (SITE / path.lstrip("/")).is_file():
        return
    missing.append((where, url, "no such file/page"))


for page in sorted(SITE.rglob("*.html")):
    rel = page.relative_to(SITE).as_posix()
    t = page.read_text(encoding="utf-8")
    t_nojs = re.sub(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", "", t, flags=re.S)
    for m in re.finditer(r'\s(?:href|src|data-poster-url|poster)="([^"]*)"', t_nojs):
        check(m.group(1), rel)
    for m in re.finditer(r'\ssrcset="([^"]*)"', t_nojs):
        for item in m.group(1).split(","):
            mm = re.match(r"^\s*(.*?)(\s+\d+(?:\.\d+)?[wx])?\s*$", item)
            check(mm.group(1), rel + " srcset")
    for m in re.finditer(r'\sdata-video-urls="([^"]*)"', t_nojs):
        for u in m.group(1).split(","):
            check(u, rel + " video")
    for m in re.finditer(r"url\(&quot;([^&]+)&quot;\)", t_nojs):
        check(m.group(1), rel + " style")
    for m in re.finditer(r'<meta [^>]*content="(https?://[^"]+)"', t):
        check(m.group(1), rel + " meta")
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', t, flags=re.S):
        for u in re.findall(r'"(https?://[^"]+)"', m.group(1)):
            if urlsplit(u).netloc in DOMAIN_HOSTS:
                check(u, rel + " json-ld")

for css in sorted((SITE / "assets/css").glob("*.css")):
    for u in re.findall(r"url\(['\"]?([^)'\"]+)['\"]?\)", css.read_text(encoding="utf-8")):
        if u.startswith(("data:", "#")):
            continue
        if not (css.parent / unquote(u)).resolve().is_file():
            missing.append((css.name, u, "css url missing"))

for where, url, why in missing:
    print(f"MISSING  {where}: {url}  ({why})")
print("\nExternal hosts still referenced:")
for host, n in external.most_common():
    print(f"  {n:4d}  {host}")
print(f"\n{len(missing)} problems")
sys.exit(1 if missing else 0)
