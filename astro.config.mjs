import { defineConfig } from 'astro/config';

// format 'file' writes about.html instead of about/index.html, so Cloudflare Pages serves /about
// directly with HTTP 200 instead of redirecting it to /about/. URLs never end in a slash.
export default defineConfig({
  site: 'https://www.esthersimsstudio.co.uk',
  output: 'static',
  trailingSlash: 'never',
  build: { format: 'file' },
});
