#!/usr/bin/env python3
"""One-off: convert the static site/ (built from the Webflow mirror) into an Astro project.

Writes src/, public/ and the page files at the repo root. Run once on the
`astro` branch; afterwards the Astro source is edited directly and this script,
build_site.py and mirror/ are kept only as an archive.
"""
import html
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from htmlspan import children  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SRC = ROOT / "src"
PUBLIC = ROOT / "public"
DOMAIN = "https://www.esthersimsstudio.co.uk"

PAGES = {  # site file -> (astro page file, component name, URL path)
    "index.html": ("index.astro", "home", "/"),
    "about.html": ("about.astro", "about", "/about"),
    "commissions.html": ("commissions.astro", "commissions", "/commissions"),
    "pricing.html": ("pricing.astro", "pricing", "/pricing"),
    "contact.html": ("contact.astro", "contact", "/contact"),
    "testimonials.html": ("testimonials.astro", "testimonials", "/testimonials"),
    "faqs.html": ("faqs.astro", "faqs", "/faqs"),
    "portfolio.html": ("portfolio.astro", "portfolio", "/portfolio"),
    "resources/privacy-policy.html": ("resources/privacy-policy.astro", "privacy-policy", "/resources/privacy-policy"),
    "resources/privacy-rights.html": ("resources/privacy-rights.astro", "privacy-rights", "/resources/privacy-rights"),
    "404.html": ("404.astro", "not-found", None),
}
SHARED = ("global-styles", "navbar_component", "footer_component")
problems = []


def norm_current(h):
    return re.sub(r' aria-current="page"', "", re.sub(r"\s*w--current", "", h))


def cls_of(op):
    m = re.search(r'class="([^"]*)"', op)
    return m.group(1) if m else ""


def head_elements(t):
    head = t[t.find("<head>") + 6 : t.find("</head>")]
    return [head[a:b] for a, b, _, _ in children(head)]


def meta(els, key):
    for e in els:
        if re.search(rf'(?:name|property)="{re.escape(key)}"', e):
            m = re.search(r'content="([^"]*)"', e)
            return html.unescape(m.group(1)) if m else None
    return None


def astro_str(s):
    return json.dumps(s, ensure_ascii=False)


def main():
    texts = {p: (SITE / p).read_text(encoding="utf-8") for p in PAGES}
    normal = [p for p in PAGES if p != "404.html"]

    # ------------------------------------------------ shared head elements
    sets = [set(head_elements(texts[p])) for p in normal]
    shared_head = set.intersection(*sets)
    ordered_shared = [e for e in head_elements(texts["index.html"]) if e in shared_head]
    ordered_shared = list(dict.fromkeys(ordered_shared))  # drop duplicate tags (index had modal.js twice)

    # Elements the layout renders itself from props
    def is_prop_el(e):
        return (
            e.startswith("<title") or e.startswith("<meta charset")
            or re.search(r'(?:name|property)="(?:description|og:title|og:description|og:image|twitter:title|twitter:description|twitter:image)"', e)
            or 'rel="canonical"' in e
            or re.search(r'href="/assets/css/(?:shared|page-[0-9a-f]{24})\.css"', e)
        )

    layout_head = [e for e in ordered_shared if not is_prop_el(e)]

    # ------------------------------------------------ shared body components
    shared_html = {}
    comp_dir = SRC / "components" / "pages"
    comp_dir.mkdir(parents=True, exist_ok=True)
    page_meta = {}

    for p, (astro_file, name, path) in PAGES.items():
        t = texts[p]
        html_tag = re.search(r"<html[^>]*>", t).group(0)
        wf_page = re.search(r'data-wf-page="([^"]+)"', html_tag).group(1)
        els = head_elements(t)
        css = re.search(r'href="/assets/css/(page-[0-9a-f]{24})\.css"', t)
        wfjs = re.search(r'src="/assets/js/(webflow-[0-9a-f]+)\.js"', t)
        title = html.unescape(re.search(r"<title>(.*?)</title>", t, re.S).group(1))
        desc = meta(els, "description")
        og_image = meta(els, "og:image")
        for k, expect in (("og:title", title), ("twitter:title", title), ("og:description", desc), ("twitter:description", desc), ("twitter:image", og_image)):
            got = meta(els, k)
            if got is not None and got != expect:
                problems.append(f"{p}: {k} differs from title/description/og:image: {got!r}")
        canonical = re.search(r'<link href="([^"]+)" rel="canonical"', t)

        # page-specific head extras = not shared, not rendered from props
        extras = [e for e in els if e not in shared_head and not is_prop_el(e)]
        (comp_dir / f"{name}.head.html").write_text("\n".join(extras) + ("\n" if extras else ""), encoding="utf-8")

        # body: split into shared pieces, page content and after-footer extras
        s = t.find("<body>") + 6
        e = t.find("</body>")
        content, after = [], []
        seen_footer = False

        def walk(a, b):
            nonlocal seen_footer
            for x, y, tag, op in children(t, a, b):
                c = cls_of(op)
                block = t[x:y]
                hit = next((k for k in SHARED if re.search(rf"\b{k}\b", c)), None)
                if hit:
                    n = norm_current(block)
                    if hit in shared_html and shared_html[hit] != n:
                        problems.append(f"{p}: {hit} differs from other pages")
                    shared_html.setdefault(hit, n)
                    if hit == "footer_component":
                        seen_footer = True
                    continue
                if re.search(r"\bpage-wrapper\b", c):
                    walk(x + len(op), y - len(f"</{tag}>"))
                    continue
                if tag == "script" and re.search(r'src="/assets/js/(?:jquery-3\.5\.1\.min|webflow-[0-9a-f]+)\.js"', op):
                    continue  # rendered by the layout
                if p == "404.html":
                    (content if tag != "script" else after).append(block)
                elif seen_footer or tag == "script":
                    after.append(block)
                else:
                    content.append(block)

        walk(s, e)
        (comp_dir / f"{name}.html").write_text("\n".join(content) + "\n", encoding="utf-8")
        (comp_dir / f"{name}.end.html").write_text("\n".join(after) + ("\n" if after else ""), encoding="utf-8")

        page_meta[p] = dict(
            astro_file=astro_file, name=name, path=path, title=title, description=desc,
            og_image=og_image, wf_page=wf_page, page_css=css.group(1) if css else None,
            webflow_js=wfjs.group(1) if wfjs else None,
            canonical=canonical.group(1) if canonical else None,
            has_page_wrapper="page-wrapper" in t,
        )
        if p != "404.html" and canonical and canonical.group(1) != DOMAIN + ("/" if path == "/" else path):
            problems.append(f"{p}: canonical {canonical.group(1)} doesn't match {path}")

    for k in SHARED:
        fname = {"global-styles": "GlobalStyles", "navbar_component": "Navigation", "footer_component": "Footer"}[k]
        (SRC / "components" / f"{fname}.html").write_text(shared_html[k] + "\n", encoding="utf-8")

    # ------------------------------------------------ layout
    (SRC / "layouts").mkdir(parents=True, exist_ok=True)
    head_block = "\n    ".join(
        re.sub(r"^<(script|style)\b", r"<\1 is:inline", el) for el in layout_head
    )
    layout = LAYOUT_TEMPLATE.replace("__SHARED_HEAD__", head_block)
    (SRC / "layouts" / "Layout.astro").write_text(layout, encoding="utf-8")

    # ------------------------------------------------ pages
    for p, m in page_meta.items():
        out = SRC / "pages" / m["astro_file"]
        out.parent.mkdir(parents=True, exist_ok=True)
        depth = m["astro_file"].count("/")
        up = "../" * (depth + 1)
        props = [
            f"title={{{astro_str(m['title'])}}}",
            f"description={{{astro_str(m['description'] or '')}}}",
        ]
        if m["path"] is not None:
            props.append(f'path="{m["path"]}"')
        if m["og_image"]:
            props.append(f'ogImage="{m["og_image"]}"')
        props += [f'wfPage="{m["wf_page"]}"']
        if m["page_css"]:
            props.append(f'pageCss="{m["page_css"]}"')
        if m["webflow_js"]:
            props.append(f'webflowJs="{m["webflow_js"]}"')
        if p == "404.html":
            props.append("bare")
        n = m["name"]
        out.write_text(
            "---\n"
            f"import Layout from '{up}layouts/Layout.astro';\n"
            f"import content from '{up}components/pages/{n}.html?raw';\n"
            f"import head from '{up}components/pages/{n}.head.html?raw';\n"
            f"import end from '{up}components/pages/{n}.end.html?raw';\n"
            "---\n"
            f"<Layout\n  " + "\n  ".join(props) + "\n  head={head}\n  end={end}\n>\n"
            "  <Fragment set:html={content} />\n"
            "</Layout>\n",
            encoding="utf-8",
        )

    # ------------------------------------------------ public/
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    shutil.copytree(SITE / "assets", PUBLIC / "assets")
    for f in ("_redirects", "robots.txt", "sitemap.xml"):
        shutil.copy2(SITE / f, PUBLIC / f)
    (PUBLIC / "_headers").write_text(HEADERS, encoding="utf-8")
    build_theme()

    for pr in problems:
        print("PROBLEM", pr)
    print(f"converted {len(page_meta)} pages; shared head elements: {len(layout_head)}")


# ---------------------------------------------------------------- theme.css
def build_theme():
    css_dir = PUBLIC / "assets" / "css"
    root_block = None
    for f in sorted(css_dir.glob("page-*.css")):
        t = f.read_text(encoding="utf-8")
        m = re.search(r":root\{[^}]*\}", t)
        if m:
            if root_block and m.group(0) != root_block:
                problems.append(f"{f.name}: :root differs")
            root_block = root_block or m.group(0)
            t = t.replace(m.group(0), "", 1)
        t = fonts_to_vars(t)
        f.write_text(t, encoding="utf-8")

    shared = css_dir / "shared.css"
    t = shared.read_text(encoding="utf-8")
    faces = re.findall(r"@font-face\{font-family:(?:Inter|Playfairdisplay) variablefont[^}]*\}", t)
    for fc in faces:
        t = t.replace(fc, "", 1)
    shared.write_text(fonts_to_vars(t), encoding="utf-8")

    decls = [d for d in root_block[len(":root{"):-1].split(";") if d]
    colours = [d for d in decls if re.search(r":#[0-9a-fA-F]{3,8}$", d)]
    typo = [d for d in decls if d not in colours]
    def block(ds):
        return "\n".join(f"  {d.split(':', 1)[0]}: {d.split(':', 1)[1]};" for d in ds)
    def face(fc):
        return re.sub(r";", ";\n  ", fc.replace("{", " {\n  ").replace("}", "\n}"))
    theme = f"""/*
 * Esther Sims Studio theme: colours, fonts and type scale.
 * Change a value here and it changes across the whole site.
 * (Extracted from the 11 per-page Webflow stylesheets, which each had a copy.)
 */

{chr(10).join(face(fc) for fc in faces)}

:root {{
  /* Fonts */
  --font-heading: "Playfairdisplay variablefont wght", sans-serif;
  --font-body: "Inter variablefont slnt wght", sans-serif;

  /* Colours */
{block(colours)}

  /* Type scale and other values */
{block(typo)}
}}
"""
    (css_dir / "theme.css").write_text(theme, encoding="utf-8")


def fonts_to_vars(t):
    t = re.sub(r"font-family:Playfairdisplay variablefont wght,sans-serif", "font-family:var(--font-heading)", t)
    t = re.sub(r"font-family:Inter variablefont slnt wght,sans-serif", "font-family:var(--font-body)", t)
    return t


HEADERS = """# Keep the pages.dev address and branch previews out of search,
# even after the same build also serves the custom domain.
https://:project.pages.dev/*
  X-Robots-Tag: noindex, nofollow

https://:version.:project.pages.dev/*
  X-Robots-Tag: noindex, nofollow
"""

LAYOUT_TEMPLATE = """---
/*
 * Shared layout for every page: head, global styles, navigation, footer and
 * Webflow's runtime (jQuery + webflow.js, which powers the nav menu and
 * interactions).
 *
 * Props
 *   title, description   page <title> and meta description (also og/twitter)
 *   path                 URL path, e.g. "/about" (canonical + current nav link)
 *   ogImage              absolute URL of the social-share image
 *   wfPage               Webflow page ID; webflow.js uses it for interactions
 *   pageCss              per-page Webflow stylesheet in /assets/css/
 *   webflowJs            Webflow runtime bundle for this page in /assets/js/
 *   head, end            raw HTML: page-specific head tags, and scripts/elements after the footer
 *   bare                 404 page: no nav/footer
 */
import globalStyles from '../components/GlobalStyles.html?raw';
import navigation from '../components/Navigation.html?raw';
import footer from '../components/Footer.html?raw';

const {
  title, description = '', path, ogImage, wfPage, pageCss, webflowJs,
  head = '', end = '', bare = false,
} = Astro.props;

const site = 'https://www.esthersimsstudio.co.uk';
const canonical = path ? new URL(path, site).href : undefined;

// Webflow marks the link to the current page with w--current + aria-current.
const markCurrent = (markup) =>
  path
    ? markup.replace(/<a ([^>]*?)href="([^"]*)"([^>]*)>/g, (tag, before, href, after) => {
        if (href !== path) return tag;
        const attrs = (before + after).replace(/class="([^"]*)"/, 'class="$1 w--current"');
        return `<a ${attrs.trim()} href="${href}" aria-current="page">`;
      })
    : markup;
---
<!DOCTYPE html>
<html data-wf-domain="www.esthersimsstudio.co.uk" data-wf-page={wfPage} data-wf-site="63ee391d6609d63fbc92b869" lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{title}</title>
    <meta name="description" content={description} />
    <meta property="og:title" content={title} />
    <meta property="og:description" content={description} />
    <meta name="twitter:title" content={title} />
    <meta name="twitter:description" content={description} />
    {ogImage && <meta property="og:image" content={ogImage} />}
    {ogImage && <meta name="twitter:image" content={ogImage} />}
    {canonical && <link rel="canonical" href={canonical} />}
    <link href="/assets/css/shared.css" rel="stylesheet" type="text/css" />
    <link href="/assets/css/theme.css" rel="stylesheet" type="text/css" />
    {pageCss && <link href={`/assets/css/${pageCss}.css`} rel="stylesheet" type="text/css" />}
    __SHARED_HEAD__
    <Fragment set:html={head} />
  </head>
  <body>
    {!bare && <Fragment set:html={globalStyles} />}
    {!bare && <Fragment set:html={markCurrent(navigation)} />}
    {bare ? <slot /> : <div class="page-wrapper"><slot /></div>}
    {!bare && <Fragment set:html={markCurrent(footer)} />}
    <script is:inline src="/assets/js/jquery-3.5.1.min.js" type="text/javascript"></script>
    {webflowJs && <script is:inline src={`/assets/js/${webflowJs}.js`} type="text/javascript"></script>}
    <Fragment set:html={end} />
  </body>
</html>
"""

if __name__ == "__main__":
    main()
