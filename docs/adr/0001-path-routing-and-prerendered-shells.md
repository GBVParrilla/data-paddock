# ADR 0001: Path routing with prerendered page shells

Status: accepted (overhaul, REVIEW #24)

## Context

The site was a single-page app on GitHub Pages using hash routes (`#/race/1`). Pages has no server, so
hash routing was the simple way to make deep links load. The cost: every page had the same `<title>`,
no description and no preview image, and link previews in chats and social apps were blank. Search
engines treat everything after `#` as one page.

Options considered:

1. **Keep hash routing.** Previews and titles can't vary by page, because crawlers never see the hash.
2. **Path routing with a `404.html` fallback only.** Deep links load, but every one is served with
   HTTP 404, which crawlers and some link unfurlers treat as a dead page, and there is still one
   generic `<title>`.
3. **Path routing plus prerendered shells.** At build time, write a copy of `index.html` for every page
   worth sharing (each race, each driver's race, the races index and the standings), each with its own
   title, description, canonical URL and Open Graph image. `404.html` is the fallback for anything else.
4. **Full server-side rendering or a static-site generator.** Most correct, but a large rewrite, and it
   would move off the static-JSON architecture the review says to keep.

## Decision

Option 3. `BrowserRouter` with the Pages base path. `frontend/scripts/prerender.mjs` runs after the data
export. It writes the shells and a sitemap, and renders a 1200×630 Open Graph image per race and per
driver-race (circuit outline plus the computed headline) with the same Playwright Chromium the crawler
uses. Old `#/…` links are rewritten to paths on load, so links already shared keep working.

## Consequences

- Shared links preview with the race or driver's headline; each page has its own title and description.
- The build gains a step of about a minute (a few hundred screenshots). Driver-race URLs are
  `/race/{id}/driver/{driver_ref}`; the selection parameters (`?session=…&drivers=…`) still work.
- The static architecture is unchanged: shells are copies of `index.html`, and the app hydrates from the
  same JSON.
