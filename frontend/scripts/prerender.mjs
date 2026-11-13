// Prerendered page shells + Open Graph images for GitHub Pages (docs/adr/0001-path-routing-and-prerendered-shells.md).
// Run after `vite build` and the data export: node scripts/prerender.mjs [distDir]
// Env: SITE_URL (absolute site root, e.g. https://user.github.io/data-paddock/), OG_IMAGES=0 to skip images.
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'

const DIST = process.argv[2] ?? 'dist'
const SITE = (process.env.SITE_URL ?? 'https://gbvparrilla.github.io/data-paddock/').replace(/\/?$/, '/')
const DATA = join(DIST, 'data')
const template = readFileSync(join(DIST, 'index.html'), 'utf8')
const read = (rel) => { const p = join(DATA, `${rel}.json`); return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : null }
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

const TEAM = { Mercedes: '#00D7B6', Ferrari: '#ED1131', 'Red Bull Racing': '#3671C6', McLaren: '#FF8000', 'Aston Martin': '#229971', Alpine: '#0093CC', Williams: '#64C4FF', 'Racing Bulls': '#6692FF', Audi: '#A6053B', 'Haas F1 Team': '#B6BABD', Cadillac: '#C9A227' }

const pages = [] // { path, title, description, image? }
const images = [] // { file, html }

function shell({ path, title, description, image }) {
  const url = SITE + path
  const meta = [
    `<title>${esc(title)}</title>`,
    `<meta name="description" content="${esc(description)}" />`,
    `<link rel="canonical" href="${esc(url)}" />`,
    `<meta property="og:site_name" content="Data Paddock" />`,
    `<meta property="og:type" content="article" />`,
    `<meta property="og:title" content="${esc(title)}" />`,
    `<meta property="og:description" content="${esc(description)}" />`,
    `<meta property="og:url" content="${esc(url)}" />`,
    image ? `<meta property="og:image" content="${esc(SITE + image)}" />\n    <meta property="og:image:width" content="1200" />\n    <meta property="og:image:height" content="630" />` : '',
    `<meta name="twitter:card" content="${image ? 'summary_large_image' : 'summary'}" />`,
  ].filter(Boolean).join('\n    ')
  const html = template
    .replace(/<title>[^<]*<\/title>/, '')
    .replace(/<meta name="description"[^>]*>/, '')
    .replace('</head>', `    ${meta}\n  </head>`)
  const out = join(DIST, path, 'index.html')
  mkdirSync(dirname(out), { recursive: true })
  writeFileSync(out, html)
}

function outlineSvg(points, color) {
  if (!points?.length) return ''
  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1])
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const pad = 40
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${p[0]} ${p[1]}`).join('') + 'Z'
  // the circuit atlas drawing: the track in ink, the team's colour along it, the start/finish line
  return `<svg viewBox="${x0 - pad} ${y0 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%">
    <path d="${d}" fill="none" stroke="#17222C" stroke-width="22" stroke-linejoin="round" stroke-linecap="round"/>
    <path d="${d}" fill="none" stroke="${color}" stroke-width="10" stroke-linejoin="round" stroke-linecap="round"/></svg>`
}

// Archivo, embedded so the images render the same offline (public/fonts, OFL)
const FONT = (() => { try { return readFileSync(new URL('../public/fonts/archivo-var.woff2', import.meta.url)).toString('base64') } catch { return '' } })()

/** An Open Graph image as a sheet from the circuit atlas: paper, a dot grid, registration marks, the race name,
 * the verdict headline and the track drawing (REVIEW_ROUND3 D6). */
function card({ kicker, title, line, sub, color, points }) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  ${FONT ? `@font-face{font-family:Archivo;src:url(data:font/woff2;base64,${FONT}) format("woff2");font-weight:100 900;font-stretch:62% 125%}` : ''}
  body{margin:0;width:1200px;height:630px;background:#EEF2F3;color:#17222C;font-family:Archivo,"Helvetica Neue",Arial,sans-serif;overflow:hidden}
  .s{position:absolute;inset:28px;border:1.5px solid #AEBAC1;background-image:radial-gradient(#C5CFD5 1.4px,transparent 1.6px);background-size:22px 22px;display:flex}
  .m{position:absolute;width:26px;height:26px;border:0 solid #17222C}
  .tl{top:-2px;left:-2px;border-width:3px 0 0 3px}.tr{top:-2px;right:-2px;border-width:3px 3px 0 0}.bl{bottom:-2px;left:-2px;border-width:0 0 3px 3px}.br{bottom:-2px;right:-2px;border-width:0 3px 3px 0}
  .l{width:600px;padding:44px 0 40px 48px;display:flex;flex-direction:column}
  .k{font-size:24px;color:#56636E;font-weight:600}
  .t{font-size:64px;font-weight:800;font-stretch:125%;line-height:1.02;margin-top:16px}
  .line{font-size:34px;font-weight:700;margin-top:26px;line-height:1.2;border-left:8px solid ${color};padding-left:18px}
  .sub{font-size:24px;color:#56636E;margin-top:16px;line-height:1.35}
  .b{margin-top:auto;font-size:24px;font-weight:700;display:flex;align-items:center;gap:12px}
  .b i{display:inline-block;width:10px;height:28px;background:#17222C}
  .r{flex:1;padding:44px 48px 44px 16px;display:flex;align-items:center}
  </style></head><body><div class="s"><span class="m tl"></span><span class="m tr"></span><span class="m bl"></span><span class="m br"></span>
  <div class="l"><div class="k">${esc(kicker)}</div><div class="t">${esc(title)}</div>
  ${line ? `<div class="line">${esc(line)}</div>` : ''}${sub ? `<div class="sub">${esc(sub)}</div>` : ''}
  <div class="b"><i></i>Data Paddock</div></div><div class="r">${outlineSvg(points, color)}</div></div></body></html>`
}

const seasons = read('seasons') ?? []
pages.push({ path: 'changes', title: 'What changed · Data Paddock', description: 'New on Data Paddock, newest first.' })
pages.push({ path: 'methods', title: 'How the numbers are made · Data Paddock', description: 'How every computed figure on Data Paddock is made: fuel-corrected pace, degradation, pit-stop places, cut lines, sector and corner ranks.' })
for (const season of seasons) {
  const year = season.year
  const events = read(`seasons/${year}/events`) ?? []
  pages.push({ path: 'races', title: `${year} races · Data Paddock`, description: `Every round of the ${year} season, with each circuit, the podium and every driver's story.` })
  pages.push({ path: `season/${year}`, title: `${year} standings · Data Paddock`, description: `The ${year} championship: the title fight, every round's results and each driver's season so far.` })
  for (const e of events.filter((x) => x.completed)) {
    const sessions = read(`events/${e.id}/sessions`) ?? []
    const race = sessions.find((s) => s.session_type === 'R' && s.ingestion.transforms)
    const w = e.winner
    const podium = (e.podium ?? []).map((d) => d.code).join(', ')
    const color = TEAM[w?.team] ?? '#17222C'
    const img = `og/race-${e.id}.png`
    // the verdict: the winner's race headline (what decided it), else who won
    const verdict = race && w ? read(`sessions/${race.id}/drivers/${w.id}/narrative`)?.headline : null
    images.push({ file: img, html: card({ kicker: `Round ${e.round}, ${year}`, title: e.name, line: verdict ?? (w ? `${w.name} won` : ''), sub: podium ? `Podium: ${podium}` : '', color, points: e.outline_preview?.points }) })
    pages.push({ path: `race/${e.id}`, title: `${e.name} ${year} · Data Paddock`, description: `${w ? `${w.name} won the ${e.name}. ` : ''}Every driver's race, told from the timing data: key moments, strategy and the story beyond the podium.`, image: img })
    if (!race) continue
    const headline = read(`sessions/${race.id}/headline`)
    for (const [id, d] of Object.entries(headline?.drivers ?? {})) {
      const story = read(`sessions/${race.id}/drivers/${id}/narrative`)
      if (!story || !d.driver_ref) continue
      const dImg = `og/race-${e.id}-${d.driver_ref}.png`
      images.push({ file: dImg, html: card({ kicker: `${e.name}, ${year}`, title: d.name, line: story.headline ?? '', sub: d.team, color: TEAM[d.team] ?? '#17222C', points: e.outline_preview?.points }) })
      pages.push({ path: `race/${e.id}/driver/${d.driver_ref}`, title: `${d.name}: ${story.headline ?? e.name} · Data Paddock`, description: story.summary ?? `${d.name}'s ${e.name}, told from the timing data.`, image: dImg })
    }
  }
}

for (const p of pages) shell(p)
writeFileSync(join(DIST, '404.html'), template) // anything else still loads the app
writeFileSync(join(DIST, 'robots.txt'), `User-agent: *\nAllow: /\nSitemap: ${SITE}sitemap.xml\n`)
writeFileSync(join(DIST, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${[SITE, ...pages.map((p) => SITE + p.path)].map((u) => `  <url><loc>${esc(u)}</loc></url>`).join('\n')}\n</urlset>\n`)
console.log(`prerender: ${pages.length} page shells`)

if (process.env.OG_IMAGES !== '0') {
  const { chromium } = await import('@playwright/test')
  const browser = await chromium.launch(process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {})
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 } })
  mkdirSync(join(DIST, 'og'), { recursive: true })
  for (const img of images) {
    await page.setContent(img.html)
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: join(DIST, img.file), type: 'png' })
  }
  await browser.close()
  console.log(`prerender: ${images.length} preview images`)
}
