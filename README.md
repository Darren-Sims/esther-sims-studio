# Esther Sims Studio website

Static version of [esthersimsstudio.co.uk](https://www.esthersimsstudio.co.uk), moved off Webflow and intended for Cloudflare Pages.

## Layout

| Path | What it is |
|---|---|
| `site/` | **The deployable site.** This is the Cloudflare Pages output folder. Generated; don't edit by hand. |
| `mirror/` | Raw `wget` mirror of the live Webflow site (19 Nov 2026). Never edited. |
| `src/` | Hand-written source files copied into `site/` (e.g. `portfolio.js`). |
| `tools/build_site.py` | Rebuilds `site/` from `mirror/` + `src/`. |
| `tools/check_site.py` | Checks that every local link in `site/` resolves, and lists external hosts. |
| `portfolio-filters.js` | Old filter script, still loaded by the live Webflow site through jsDelivr. Keep it until the switch to Cloudflare Pages, then delete it. |

## Rebuild

```bash
python3 tools/build_site.py
python3 tools/check_site.py
```

## Cloudflare Pages settings

- Build command: *(none)*
- Build output directory: `site`
- Cloudflare Pages serves `/about` from `about.html` and uses `404.html` for unknown paths.

## What the build changes

- Pages sit at the root with the same URLs as the live site. The five `contact?size=…` copies that wget saved are dropped, because one `contact.html` handles every query string.
- Assets are moved to `assets/css`, `assets/js` and `assets/media`. Internal links become clean root paths (`/about`, `/contact?size=A5&price=105`).
- Canonical, `og:image` and JSON-LD URLs become absolute on the real domain.
- Fixed:
  - the homepage background-image URLs wget mangled
  - the `webflow.io` links in the `/commissions` tooltips
  - the preconnect to Webflow's CDN
  - SRI hashes on files that are now local
- Portfolio: `assets/js/portfolio.js` replaces both the jsDelivr filters script and the inline Load More script. One render step filters first, then pages through the results, which fixes the clash between the two. Back-to-top now checks on scroll and resize, with a fallback for short pages.

## Still to do

- [x] **Forms:** commission form on `/contact` → Formspree (`src/forms.js`); pop-up nav form replaced with an email button + link to `/contact` until the footer redesign.
- [ ] **Instagram feeds:** two Finsweet Components feeds (home page) depend on Finsweet's Webflow app and a token saved against the Webflow site. They need replacing.
- [x] **Back-to-top on desktop:** Brave Shields hid `.back-to-top`; renamed to `.scroll-top-btn`.
- [x] **Homepage JSON-LD:** placeholder `VideoObject` removed (Search Console: "Video isn't on a watch page"). Also removed the invalid self-published reviews from `/about`'s JSON-LD.
- [ ] **Per-page assets:** the site still has one CSS file per page (plus `shared.css`) and four `webflow.js` bundles. Webflow builds these per page, so merging them needs testing on the preview.
- [ ] **Third-party scripts:** Tippy.js and Popper.js v1/v4 load from unpkg on `/commissions`. Self-host or upgrade them.
- [ ] **Portfolio indexing:** `/portfolio` is `noindex` and left out of `sitemap.xml`, matching the live site. Decide whether to keep that.
