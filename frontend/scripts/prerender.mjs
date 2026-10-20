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
  return `<svg viewBox="${x0 - pad} ${y0 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%">
    <path d="${d}" fill="none" stroke="${color}" stroke-width="16" stroke-linejoin="round" stroke-linecap="round"/></svg>`
}

function card({ kicker, title, line, sub, color, points }) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  body{margin:0;width:1200px;height:630px;background:#0c0e11;color:#e7e9ec;font-family:Inter,"Helvetica Neue",Arial,sans-serif;display:flex;overflow:hidden}
  .l{width:640px;padding:64px 0 56px 72px;display:flex;flex-direction:column}
  .k{font-size:22px;letter-spacing:.08em;text-transform:uppercase;color:#8b929c;font-weight:600}
  .t{font-size:66px;font-weight:800;line-height:1.02;letter-spacing:-.03em;margin-top:20px}
  .bar{width:72px;height:6px;border-radius:3px;background:${color};margin-top:30px}
  .line{font-size:32px;font-weight:600;margin-top:24px;line-height:1.25}
  .sub{font-size:24px;color:#a8aeb6;margin-top:14px;line-height:1.35}
  .b{margin-top:auto;font-size:24px;font-weight:700;display:flex;align-items:center;gap:12px}
  .b i{display:inline-block;width:12px;height:30px;background:#e7e9ec;border-radius:2px}.b em{display:inline-block;width:14px;height:14px;background:#e10600;border-radius:2px;align-self:flex-start}
  .r{flex:1;padding:56px 64px 56px 24px;display:flex;align-items:center}
  </style></head><body><div class="l"><div class="k">${esc(kicker)}</div><div class="t">${esc(title)}</div><div class="bar"></div>
  <div class="line">${esc(line)}</div>${sub ? `<div class="sub">${esc(sub)}</div>` : ''}
  <div class="b"><i></i><em></em>Data Paddock</div></div><div class="r">${outlineSvg(points, color)}</div></body></html>`
}

const seasons = read('seasons') ?? []
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
    const podium = (e.podium ?? []).map((d) => d.code).join(' · ')
    const color = TEAM[w?.team] ?? '#e7e9ec'
    const img = `og/race-${e.id}.png`
    images.push({ file: img, html: card({ kicker: `Round ${e.round} · ${year}`, title: e.name, line: w ? `${w.name} won` : '', sub: podium ? `Podium: ${podium}` : '', color, points: e.outline_preview?.points }) })
    pages.push({ path: `race/${e.id}`, title: `${e.name} ${year} · Data Paddock`, description: `${w ? `${w.name} won the ${e.name}. ` : ''}Every driver's race, told from the timing data: key moments, strategy and the story beyond the podium.`, image: img })
    if (!race) continue
    const headline = read(`sessions/${race.id}/headline`)
    for (const [id, d] of Object.entries(headline?.drivers ?? {})) {
      const story = read(`sessions/${race.id}/drivers/${id}/narrative`)
      if (!story || !d.driver_ref) continue
      const dImg = `og/race-${e.id}-${d.driver_ref}.png`
      images.push({ file: dImg, html: card({ kicker: `${e.name} · ${year}`, title: d.name, line: story.headline ?? '', sub: d.team, color: TEAM[d.team] ?? '#e7e9ec', points: e.outline_preview?.points }) })
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
    await page.screenshot({ path: join(DIST, img.file), type: 'png' })
  }
  await browser.close()
  console.log(`prerender: ${images.length} preview images`)
}
