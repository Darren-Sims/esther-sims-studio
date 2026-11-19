#!/usr/bin/env python3
"""Build the deployable site/ folder from the raw wget mirror in mirror/.

mirror/ is never modified. Re-running this script rebuilds site/ from scratch.

What it does:
  * Pages  -> site/<name>.html at the root (Cloudflare Pages serves /about from
              about.html), keeping the live URL paths. Drops the duplicate
              contact?size=... copies that wget saved for each query string.
  * Assets -> site/assets/{css,js,media}/ with stable names.
  * Links  -> internal links become clean root paths (/about, /commissions#x,
              /contact?size=A5&price=105); asset links become /assets/...;
              canonical, og:image and JSON-LD URLs become absolute on the real domain.
  * Fixes  -> background-image URLs that wget mangled, webflow.io links,
              the preconnect to Webflow's CDN, SRI hashes on local files,
              and the jsDelivr portfolio-filters.js + inline Load More script
              (replaced by /assets/js/portfolio.js).
"""
import html
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parent.parent
MIRROR = ROOT / "mirror"
SITE = ROOT / "site"
DOMAIN = "https://www.esthersimsstudio.co.uk"
WEBFLOW_SITE_ID = "63ee391d6609d63fbc92b869"
CDN = "cdn.prod.website-files.com"
CLOUDFRONT = "d3e54v103j8qbb.cloudfront.net"
PAGES_DIR = MIRROR / "www.esthersimsstudio.co.uk"

# mirror page path (relative to PAGES_DIR) -> output file (relative to SITE)
PAGES = {
    "index.html": "index.html",
    "about.html": "about.html",
    "commissions/index.html": "commissions.html",
    "pricing.html": "pricing.html",
    "contact.html": "contact.html",
    "testimonials.html": "testimonials.html",
    "faqs.html": "faqs.html",
    "portfolio.html": "portfolio.html",
    "resources/privacy-policy.html": "resources/privacy-policy.html",
    "resources/privacy-rights.html": "resources/privacy-rights.html",
    "404.html": "404.html",
}

warnings = []


# ---------------------------------------------------------------- assets
def asset_target(mirror_rel: str) -> str:
    """Map a mirror-relative asset path to its path under site/ (no leading slash)."""
    p = mirror_rel
    name = p.rsplit("/", 1)[-1]
    if p.startswith(f"{CLOUDFRONT}/js/jquery"):
        return "assets/js/jquery-3.5.1.min.js"
    if "finsweetcomponentsconfig" in p:
        return "assets/js/finsweetcomponentsconfig-1.0.15.js"
    if p.startswith(f"{CDN}/{WEBFLOW_SITE_ID}/css/"):
        # esthersimsstudio.webflow.<pageid>.<hash>.opt.min.css -> page-<pageid>.css
        m = re.match(r"esthersimsstudio\.webflow\.([0-9a-f]{24})\.", name)
        if m:
            return f"assets/css/page-{m.group(1)}.css"
        if ".shared." in name:
            return "assets/css/shared.css"
        return f"assets/css/{name}"
    if p.startswith(f"{CDN}/{WEBFLOW_SITE_ID}/js/"):
        # webflow.<chunk>.<hash>.js -> webflow-<chunk>.js
        m = re.match(r"webflow\.([0-9a-f]+)\.", name)
        return f"assets/js/webflow-{m.group(1)}.js" if m else f"assets/js/{name}"
    return f"assets/media/{name}"


def copy_assets():
    mapping = {}
    for host in (CDN, CLOUDFRONT):
        for f in sorted((MIRROR / host).rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(MIRROR).as_posix()
            tgt = asset_target(rel)
            if tgt in mapping.values():
                warnings.append(f"asset name clash: {rel} -> {tgt}")
            mapping[rel] = tgt
            dest = SITE / tgt
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
    return mapping


def fix_css(mapping):
    """CSS moved from .../css/ to assets/css/; fonts etc. now live in assets/media/."""
    for css in (SITE / "assets/css").glob("*.css"):
        text = css.read_text(encoding="utf-8")

        def repl(m):
            q, url = m.group(1), m.group(2)
            if url.startswith(("data:", "http:", "https:", "#")):
                return m.group(0)
            name = unquote(url.split("?")[0]).rsplit("/", 1)[-1]
            if not (SITE / "assets/media" / name).exists():
                warnings.append(f"{css.name}: url({url}) has no local file")
            return f"url({q}../media/{url.rsplit('/', 1)[-1]}{q})"

        text = re.sub(r"url\((['\"]?)([^)'\"]+)\1\)", repl, text)
        text = text.replace(".back-to-top", ".scroll-top-btn")  # see step 12 in process_page
        css.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- pages
def page_url(out_rel: str) -> str:
    if out_rel == "index.html":
        return "/"
    return "/" + out_rel[: -len(".html")]


MIRROR_TO_URL = {m: page_url(o) for m, o in PAGES.items()}


def resolve_internal(target_rel: str, frag: str) -> str | None:
    """target_rel is a mirror-page-relative path like 'commissions/index.html' or
    'contact?size=A5&price=105.html'. Return the clean URL, or None if unknown."""
    if target_rel in MIRROR_TO_URL:
        return MIRROR_TO_URL[target_rel] + frag
    m = re.fullmatch(r"(contact)\?(.+)\.html", target_rel)
    if m:
        return f"/contact?{m.group(2)}{frag}"
    return None


def rewrite_url(raw: str, page_rel: str, mapping, absolute=False) -> str:
    """Rewrite one URL found in a page at PAGES_DIR/page_rel."""
    url = html.unescape(raw).strip()
    if not url or url.startswith(("mailto:", "tel:", "#", "data:", "javascript:")):
        return raw
    # Absolute links to the Webflow CDN / cloudfront
    for host in (CDN, CLOUDFRONT):
        for prefix in (f"https://{host}/", f"http://{host}/", f"//{host}/"):
            if url.startswith(prefix):
                rel = unquote(f"{host}/" + url[len(prefix):])
                tgt = mapping.get(rel)
                if tgt is None:
                    # wget saves query strings into the filename
                    tgt = next((t for r, t in mapping.items() if r.split("?")[0] == rel.split("?")[0]), None)
                if tgt is None:
                    warnings.append(f"{page_rel}: no local file for {url}")
                    return raw
                path = "/" + quote_path(tgt)
                return html.escape(DOMAIN + path if absolute else path, quote=True)
    if re.match(r"^[a-z]+://", url):
        # Old Webflow staging domain -> real domain
        url2 = re.sub(r"^https?://esthersimsstudio\.webflow\.io", DOMAIN, url)
        return html.escape(url2, quote=True)
    # Relative path inside the mirror
    base = f"http://m/www.esthersimsstudio.co.uk/{page_rel}"
    joined = urlsplit(urljoin(base, url))
    path = unquote(joined.path)
    frag = f"#{joined.fragment}" if joined.fragment else ""
    if path.startswith("/www.esthersimsstudio.co.uk/"):
        target_rel = path[len("/www.esthersimsstudio.co.uk/"):]
        if joined.query:  # unlikely; wget folds queries into names
            target_rel += "?" + joined.query
        # Webflow writes href="#" as a link to the page itself plus an empty fragment
        if url.endswith("#") and not joined.fragment and target_rel == page_rel:
            return "#"
        clean = resolve_internal(target_rel, frag)
        if clean is None:
            warnings.append(f"{page_rel}: unknown internal link {url}")
            return raw
        return html.escape(DOMAIN + clean if absolute else clean, quote=True)
    rel = path.lstrip("/")
    tgt = mapping.get(rel) or next((t for r, t in mapping.items() if r.split("?")[0] == rel.split("?")[0]), None)
    if tgt is None:
        warnings.append(f"{page_rel}: unresolved relative URL {url}")
        return raw
    out = "/" + quote_path(tgt) + frag
    return html.escape(DOMAIN + out if absolute else out, quote=True)


def quote_path(p: str) -> str:
    return p.replace("%", "%25").replace(" ", "%20").replace("(", "%28").replace(")", "%29").replace(",", "%2C")


PORTFOLIO_SCRIPT_TAG = '<script src="/assets/js/portfolio.js" defer></script>'


def process_page(src_rel: str, out_rel: str, mapping):
    text = (PAGES_DIR / src_rel).read_text(encoding="utf-8")

    # 1. Mangled background images: url(https://www.esthersimsstudio.co.uk/&quot;https://cdn/...&quot;)
    text = re.sub(
        r"url\(https://www\.esthersimsstudio\.co\.uk/&quot;(https://[^&]+)&quot;\)",
        r"url(&quot;\1&quot;)",
        text,
    )

    # 2. Drop the preconnect to Webflow's CDN and SRI on local assets
    text = re.sub(r'<link href="https://cdn\.prod\.website-files\.com" rel="preconnect"[^>]*/?>', "", text)

    # 3. JSON-LD blocks: absolute URLs on the real domain
    def jsonld(m):
        body = re.sub(
            r'"(https://(?:cdn\.prod\.website-files\.com|esthersimsstudio\.webflow\.io)[^"]*)"',
            lambda u: '"' + html.unescape(rewrite_url(u.group(1), src_rel, mapping, absolute=True)) + '"',
            m.group(2),
        )
        return m.group(1) + body + m.group(3)

    text = re.sub(r'(<script type="application/ld\+json">)(.*?)(</script>)', jsonld, text, flags=re.S)

    # 4. <meta content="..."> with URLs (og:image etc.) -> absolute
    text = re.sub(
        r'(<meta [^>]*content=")(https?://[^"]+|\.\./[^"]+)(")',
        lambda m: m.group(1) + rewrite_url(m.group(2), src_rel, mapping, absolute=True) + m.group(3),
        text,
    )

    # 5. Canonical -> absolute
    text = re.sub(
        r'(<link href=")([^"]+)(" rel="canonical"\s*/?>)',
        lambda m: m.group(1) + rewrite_url(m.group(2), src_rel, mapping, absolute=True) + m.group(3),
        text,
    )

    # 6. Single-URL attributes
    def attr(m):
        return m.group(1) + rewrite_url(m.group(2), src_rel, mapping) + m.group(3)

    text = re.sub(r'(\s(?:href|src|data-poster-url|poster)=")([^"]*)(")', attr, text)

    # 7. List attributes: srcset ("url 500w, url 800w") and data-video-urls ("a.mp4,b.webm")
    def srcset(m):
        parts = []
        for item in m.group(2).split(","):
            item = item.strip()
            if not item:
                continue
            # filenames can contain spaces; descriptors are the trailing token like 500w
            mm = re.match(r"^(.*?)(\s+\d+(?:\.\d+)?[wx])?$", item)
            parts.append(rewrite_url(mm.group(1), src_rel, mapping) + (mm.group(2) or ""))
        return m.group(1) + ", ".join(parts) + m.group(3)

    text = re.sub(r'(\ssrcset=")([^"]*)(")', srcset, text)
    text = re.sub(
        r'(\sdata-video-urls=")([^"]*)(")',
        lambda m: m.group(1) + ",".join(rewrite_url(u, src_rel, mapping) for u in m.group(2).split(",")) + m.group(3),
        text,
    )

    # 8. style="...url(&quot;...&quot;)..."
    text = re.sub(
        r"url\(&quot;([^&]+)&quot;\)",
        lambda m: "url(&quot;" + rewrite_url(m.group(1), src_rel, mapping) + "&quot;)",
        text,
    )

    # 9. Remove integrity/crossorigin on now-local scripts and styles (SRI is for third-party CDNs)
    text = re.sub(r'(<(?:script|link)\b[^>]*?(?:src|href)="/assets/[^"]*"[^>]*?)\s+integrity="[^"]*"', r"\1", text)
    text = re.sub(r'(<(?:script|link)\b[^>]*?(?:src|href)="/assets/[^"]*"[^>]*?)\s+crossorigin="[^"]*"', r"\1", text)

    # 10. webflow.io links inside escaped HTML (tooltips stored in attributes / JSON)
    text = text.replace("https://esthersimsstudio.webflow.io", DOMAIN)

    # 11. Portfolio: replace the jsDelivr filters script and the inline Load More script
    if src_rel == "portfolio.html":
        n_before = text.count("portfolio-filters.js")
        text = re.sub(r'<script src="https://cdn\.jsdelivr\.net/gh/darren-sims/esther-sims-studio/portfolio-filters\.js"></script>', "", text)
        text, n = re.subn(r"<script>\s*\(function \(\) \{\s*var PAGE_SIZE = 9;.*?\}\)\(\);\s*</script>", PORTFOLIO_SCRIPT_TAG, text, flags=re.S)
        if n_before != 1 or n != 1:
            warnings.append(f"portfolio.html: expected 1 filters tag and 1 Load More script, found {n_before} and {n}")

    # 12. Ad blockers' "annoyance" lists (e.g. Brave Shields) hide anything called
    #     back-to-top, so give the button neutral names.
    text = text.replace("data-back-to-top", "data-scroll-top").replace("back-to-top", "scroll-top-btn")

    out = SITE / out_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- extras
def write_extras():
    urls = [page_url(o) for o in PAGES.values() if o not in ("404.html", "portfolio.html")]
    # portfolio.html is noindex on the live site, so it is left out of the sitemap to match.
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{DOMAIN}{'' if u == '/' else u}</loc></url>" for u in urls]
    sm.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    (SITE / "robots.txt").write_text(f"Sitemap: {DOMAIN}/sitemap.xml\n", encoding="utf-8")
    # Redirect the bare domain to www to match the live site
    (SITE / "_redirects").write_text(
        "# Keep old .html and trailing-slash URLs working\n"
        "/commissions/  /commissions  301\n"
        "/commissions/index.html  /commissions  301\n",
        encoding="utf-8",
    )
    src = ROOT / "src" / "portfolio.js"
    shutil.copy2(src, SITE / "assets/js/portfolio.js")


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    mapping = copy_assets()
    fix_css(mapping)
    for src_rel, out_rel in PAGES.items():
        process_page(src_rel, out_rel, mapping)
    write_extras()
    for w in warnings:
        print("WARN", w, file=sys.stderr)
    print(f"built {len(PAGES)} pages, {len(mapping)} assets, {len(warnings)} warnings")


if __name__ == "__main__":
    main()
