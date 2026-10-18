// Measures how busy pages are, so declutter work has numbers rather than impressions.
// Usage: node scripts/page-metrics.mjs <base url> [out.json] [screenshot dir]
// e.g.   node scripts/page-metrics.mjs http://127.0.0.1:4173/data-paddock/ metrics.json shots/
import { chromium } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'

const BASE = (process.argv[2] ?? 'http://127.0.0.1:4173/data-paddock/').replace(/\/?$/, '/')
const OUT = process.argv[3]
const SHOTS = process.argv[4]
const PAGES = [
  ['home', ''],
  ['races', 'races'],
  ['standings', 'season/2026'],
  ['race-1', 'race/1'],
  ['race-12', 'race/12'],
  ['race-17', 'race/17'],
  ['driver-gasly', 'race/1/driver/gasly'],
  ['driver-gasly-expert', 'race/1/driver/gasly?mode=expert'],
]
const WIDTHS = [1360, 375]

const browser = await chromium.launch(process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {})
const rows = []
if (SHOTS) mkdirSync(SHOTS, { recursive: true })
for (const width of WIDTHS) {
  const page = await browser.newPage({ viewport: { width, height: 900 } })
  for (const [name, path] of PAGES) {
    await page.goto(BASE + path)
    await page.waitForLoadState('networkidle')
    // scroll through once so lazily loaded charts take their real height
    for (let y = 0; y < 12000; y += 700) { await page.evaluate((v) => window.scrollTo(0, v), y); await page.waitForTimeout(60) }
    await page.waitForLoadState('networkidle')
    await page.evaluate(() => window.scrollTo(0, 0))
    const m = await page.evaluate(() => {
      const main = document.querySelector('main')
      const panels = [...(main?.querySelectorAll('.panel') ?? [])].filter((el) => !el.parentElement?.closest('.panel') && (el).offsetHeight > 0)
      const terms = [...document.querySelectorAll('main .term')].map((t) => t.textContent?.trim() ?? '')
      return {
        height: document.documentElement.scrollHeight,
        panels: panels.length,
        underlines: terms.length,
        underlineTerms: terms,
        title: document.title,
        footer: document.querySelector('footer')?.textContent?.trim() ?? '',
        scrollsSideways: document.documentElement.scrollWidth > window.innerWidth + 1,
      }
    })
    rows.push({ page: name, width, ...m })
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}-${width}.png`, fullPage: true })
    console.log(`${name.padEnd(20)} ${String(width).padStart(4)}px  height ${String(m.height).padStart(5)}  panels ${m.panels}  underlines ${m.underlines}${m.scrollsSideways ? '  SIDEWAYS' : ''}  "${m.title}"`)
  }
  await page.close()
}
await browser.close()
if (OUT) writeFileSync(OUT, JSON.stringify(rows, null, 2))
