# Esther Sims Studio website

Astro static site for [esthersimsstudio.co.uk](https://www.esthersimsstudio.co.uk), hosted on Cloudflare Pages. Rebuilt from the Webflow site in November 2026.

## Local development

Use the Node version in `.node-version` (22). On a new checkout run `npm install`, then:

- `npm run dev` — local dev server with live reload
- `npm run build` — build the static site into `dist/`
- `npm run preview` — serve the built site locally

## Where things live

| To change… | Edit |
|---|---|
| **Colours, fonts, type scale** | `public/assets/css/theme.css`. One place for the whole site: `--green-black`, `--sage-green`, `--gold-yellow`…, `--font-heading` / `--font-body`, and the h1–h4/paragraph sizes. |
| **Navigation** (pop-up menu) | `src/components/Navigation.html` |
| **Footer** | `src/components/Footer.html` |
| **A page's content** | `src/components/pages/<page>.html`, e.g. `home.html`, `about.html`. Plain HTML using the Webflow class names. |
| **A page's title, description, share image** | the props in `src/pages/<page>.astro` |
| **A page's structured data / extra head tags** | `src/components/pages/<page>.head.html` |
| **Scripts or elements after the footer** | `src/components/pages/<page>.end.html` |
| **Head tags, scripts and wrappers on every page** | `src/layouts/Layout.astro` |
| **Images, video, fonts, PDFs** | `public/assets/media/`, referenced as `/assets/media/<file>` |
| **Site scripts** | `public/assets/js/`: `portfolio.js` (filters, Load more, back-to-top) and `forms.js` (Formspree) |
| **Redirects / headers** | `public/_redirects`, `public/_headers` |

### Spacing

Spacing comes from the Webflow utility classes in the HTML, such as `padding-global`, `padding-section-large`, `margin-bottom margin-small` and `max-width-large`. To change one element, change its classes in the page's `.html`. To change a spacing step everywhere, edit that class in the CSS.

The CSS is still Webflow's: `shared.css` plus one minified `page-<id>.css` per page. Each page file repeats most of the site's styles, so a site-wide CSS change currently has to go in every page file. Merging them into one readable stylesheet is the next clean-up step (see To do).

### Adding an image

1. Save it to `public/assets/media/`. Keep files reasonably small: export at about 2× the largest size it will show, as WebP or AVIF.
2. Reference it in the page HTML: `<img src="/assets/media/my-image.webp" alt="…" loading="lazy" width="…" height="…">`.

Astro's automatic image optimisation (`<Image />` from `astro:assets`) needs the section to be an `.astro` component rather than a raw `.html` file. Convert a section when you want that.

### Current page in the nav

`Layout.astro` adds Webflow's `w--current` class and `aria-current="page"` to any nav or footer link whose `href` matches the page's `path` prop. Don't hard-code them in the HTML.

## Webflow runtime

The pages still load jQuery and Webflow's `webflow.js` (`public/assets/js/webflow-*.js` plus its `webflow.achunk.*.js` chunks). They power the nav menu, sliders and interactions, which are tied to each page's `wfPage` ID. Keep them until those features are rewritten.

## Cloudflare Pages

- Framework preset: **Astro**
- Build command: `npm run build`
- Build output directory: `dist`
- Node version comes from `.node-version`.
- `public/_headers` keeps the `pages.dev` address and branch previews out of search. The custom domain is indexable.

Every branch gets its own preview URL. Make changes on a branch, check the preview, then merge to `main` to go live.

## Archive

`archive/` holds the migration record: the raw `wget` mirror of the Webflow site (`archive/mirror/`) and the scripts that turned it into this project (`archive/tools/`). Nothing in the build uses it.

`portfolio-filters.js` at the repo root is still loaded by the live Webflow site through jsDelivr. Delete it after the domain switch.

## To do

- [ ] **Instagram feed → Behold:** replace the two Finsweet feeds on the homepage with a Behold JSON feed.
- [ ] **Merge the per-page CSS** into one readable stylesheet, checking each page on a branch preview.
- [ ] **`/about`:** remove the Webflow debug style that outlines `href="#"` links in yellow (`src/components/pages/about.end.html`).
- [ ] **Self-host or upgrade** Tippy.js v4 and Popper.js v1 on `/commissions` (loaded from unpkg).
- [ ] **Privacy policy:** add Site Pulse if it collects personal data or sets cookies; add Behold when the feed goes live.
- [ ] **After switch-over:** "Validate fix" in Search Console for the video and review-snippet issues; cancel the Webflow site plan.
